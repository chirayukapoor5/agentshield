"""Mock-first OpenAI-compatible client with SQLite request ledger and durable cache.

Real network calls require explicit provider configuration, nonzero USD allowance and
concrete request/token/$ caps. The ledger is shared by all client instances pointing
to the same DB. A reservation is charged before each network attempt (including retries).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml


class BudgetExceeded(RuntimeError):
    pass


class ConfigError(ValueError):
    pass


def load_config(path="config/api.yaml"):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ConfigError("API config must be a mapping")
    provider = cfg.get("provider")
    if provider not in ("mock", "openai_compatible"):
        raise ConfigError("provider must be mock or openai_compatible")
    models = cfg.get("models", {})
    if provider != "mock":
        mandatory = [cfg.get("base_url"), models.get("victim"), models.get("attacker"),
                     models.get("translator")]
        if any(not isinstance(x, str) or not x or x == "FILL_IN" for x in mandatory):
            raise ConfigError("configure URL and role-specific model IDs before real API calls")
        if models["victim"] == models["attacker"]:
            raise ConfigError("victim and attacker must use distinct model IDs")
    return cfg


class Client:
    def __init__(self, config=None, ledger="data/cache/requests.sqlite3",
                 cache_dir="data/cache/responses", transport=None, clock=time.time,
                 sleep=time.sleep):
        self.config = load_config() if config is None else config
        self.provider = self.config["provider"]
        self.models = self.config.get("models", {})
        self.limits = self.config.get("limits", {})
        self.request = self.config.get("request", {})
        self.clock, self.sleep = clock, sleep
        self.transport = transport or self._http_transport
        self.ledger_path = Path(ledger)
        self.cache_dir = Path(cache_dir)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mutex = threading.RLock()
        with self._db() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY, ts REAL NOT NULL, cache_key TEXT NOT NULL,
                role TEXT NOT NULL, tokens_reserved INTEGER NOT NULL, usd_reserved REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL
            )""")
            con.execute("CREATE INDEX IF NOT EXISTS requests_ts ON requests(ts)")
        if self.provider != "mock":
            for field in ("max_requests_per_min", "max_tokens_per_min", "max_total_requests"):
                if type(self.limits.get(field)) is not int or self.limits[field] <= 0:
                    raise ConfigError(f"{field} must be a positive integer for real calls")
            if float(self.limits.get("max_total_usd", 0)) <= 0:
                raise ConfigError("max_total_usd=0 disables all paid calls (fail closed)")
            if type(self.limits.get("max_usd_per_request")) not in (int, float) or self.limits["max_usd_per_request"] <= 0:
                raise ConfigError("positive max_usd_per_request required for USD budget reservation")
            if not os.environ.get(self.config.get("api_key_env", "API_KEY")):
                raise ConfigError("configured API key environment variable is missing")
            if self.models["victim"] == self.models["attacker"]:
                raise ConfigError("victim and attacker IDs must differ")
            for role in ("victim", "attacker", "translator"):
                if self.models.get(role) in (None, "", "FILL_IN"):
                    raise ConfigError(f"missing {role} model ID")
            if self.config.get("base_url") in ("", "FILL_IN", None):
                raise ConfigError("base_url is required for real calls")

    def _db(self):
        con = sqlite3.connect(self.ledger_path, timeout=30)
        con.execute("PRAGMA busy_timeout=30000")
        return con

    def _reserve(self, key, role, model, tokens):
        """Reserve a request globally, fail closed rather than silently exceed a cap."""
        with self._mutex:
            with self._db() as con:
                con.execute("BEGIN IMMEDIATE")
                total, reserved_usd = con.execute("SELECT COUNT(*), COALESCE(SUM(usd_reserved),0) FROM requests WHERE provider != 'mock'").fetchone()
                last = self.clock() - 60
                used, toks = con.execute(
                    "SELECT COUNT(*), COALESCE(SUM(tokens_reserved),0) FROM requests WHERE ts > ? AND provider != 'mock'",
                    (last,)).fetchone()
                if reserved_usd + self.limits["max_usd_per_request"] > self.limits["max_total_usd"] + 1e-9:
                    raise BudgetExceeded("USD cap reached")
                if total >= self.limits["max_total_requests"]:
                    raise BudgetExceeded("global total request cap reached")
                if used >= self.limits["max_requests_per_min"]:
                    raise BudgetExceeded("request-per-minute cap reached: retry after window")
                if toks + tokens > self.limits["max_tokens_per_min"]:
                    raise BudgetExceeded("reserved token-per-minute cap reached")
                con.execute(
                    "INSERT INTO requests(ts,cache_key,role,tokens_reserved,usd_reserved,status,provider,model) VALUES (?,?,?,?,?,?,?,?)",
                    (self.clock(), key, role, tokens, self.limits["max_usd_per_request"], "reserved", self.provider, model))
                return con.execute("SELECT last_insert_rowid()").fetchone()[0]

    def _record(self, key, role, model, tokens, status):
        with self._db() as con:
            con.execute(
                "INSERT INTO requests(ts,cache_key,role,tokens_reserved,usd_reserved,status,provider,model) VALUES (?,?,?,?,?,?,?,?)",
                (self.clock(), key, role, tokens, 0, status, self.provider, model))

    def _finish(self, request_id, status):
        with self._db() as con:
            con.execute("UPDATE requests SET status=? WHERE id=?", (status, request_id))

    @staticmethod
    def _http_transport(url, key, payload, timeout):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url.rstrip("/") + "/chat/completions", data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read())

    def chat(self, role, messages, *, temperature=None, max_tokens=None, retries=3, extra=None):
        if role not in ("victim", "attacker", "translator"):
            raise ValueError("unrecognized role")
        if not isinstance(messages, list):
            raise TypeError("messages must be a list")
        model = self.models.get(role, "mock-" + role) if self.provider != "mock" else "mock-" + role
        params = {
            "temperature": self.request.get("temperature", 0.0) if temperature is None else temperature,
            "max_tokens": self.request.get("max_tokens", 1024) if max_tokens is None else max_tokens,
        }
        payload = {"model": model, "messages": messages, **params}
        if extra is not None:
            if not isinstance(extra, dict) or any(k in payload for k in extra):
                raise ValueError("invalid or overlapping extra OpenAI-compatible parameters")
            payload.update(extra)
        key = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = self.cache_dir / (key + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        if self.provider == "mock":
            # Deterministic, explicitly not a simulation of AgentDojo behavior.
            response = {"id": "mock-" + key[:16], "model": model, "created_utc": "MOCK",
                        "choices": [{"message": {"role": "assistant",
                            "content": "MOCK_RESPONSE_" + key[:12]}}],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        "_mock": True}
            self._record(key, role, model, 0, "mock")
        else:
            # Conservative estimate; project cap is on *reserved* not billed tokens.
            estimate = max(1, len(json.dumps(messages, ensure_ascii=False)) // 3) + int(params["max_tokens"])
            api_key = os.environ[self.config.get("api_key_env", "API_KEY")]
            last_error = None
            for attempt in range(retries + 1):
                reservation = self._reserve(key, role, model, estimate)
                try:
                    response = self.transport(self.config["base_url"], api_key, payload,
                                              float(self.request.get("timeout_s", 60)))
                    self._finish(reservation, "ok")
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                    self._finish(reservation, "error")
                    last_error = exc
                    retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in (429, 500, 502, 503, 504)
                    if attempt == retries or not retryable:
                        raise
                    self.sleep(min(30, 2 ** attempt + random.Random(key + str(attempt)).random()))
            else:
                raise last_error
        # Atomic cache replacement; never store API credentials in cached response.
        temporary = path.with_suffix(".tmp." + str(os.getpid()) + "." + str(threading.get_ident()))
        temporary.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
        return response

    def usage(self):
        with self._db() as con:
            rows = con.execute("SELECT provider, status, COUNT(*), SUM(tokens_reserved), SUM(usd_reserved) FROM requests GROUP BY provider,status").fetchall()
        return [{"provider": p, "status": s, "requests": n, "reserved_tokens": t, "reserved_usd": usd} for p,s,n,t,usd in rows]
