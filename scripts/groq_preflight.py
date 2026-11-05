"""Groq free-tier preflight. Explicitly limited to at most 20 chat calls.

Never logs the API key or request/response contents; model list is public metadata.
This does not run AgentDojo or determine a provider's true rate-limit ceiling.
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE_URL = "https://api.groq.com/openai/v1"


def request_json(url, token, payload=None, timeout=30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if payload is not None else "GET",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "AgentShield-research-preflight/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def preflight(token, model, count=20, sleep_seconds=6, timeout=30,
              request=request_json, sleep=time.sleep):
    if not token:
        raise RuntimeError("GROQ_API_KEY secret unavailable")
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError("hard cap: 1–20 chat-completion calls")
    if sleep_seconds < 0:
        raise ValueError("sleep must not be negative")
    catalog = request(BASE_URL + "/models", token, timeout=timeout)
    model_ids = sorted(
        m["id"] for m in catalog.get("data", [])
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    )
    if model not in model_ids:
        return {
            "result": "model_unavailable",
            "available_model_ids": model_ids,
            "selected_model": model,
            "chat_calls_attempted": 0,
            "chat_calls_succeeded": 0,
        }
    attempts = []
    for i in range(count):
        if i:
            sleep(sleep_seconds)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Respond with OK."}],
            "temperature": 0,
            "max_tokens": 8,
        }
        started = time.monotonic()
        try:
            reply = request(BASE_URL + "/chat/completions", token,
                            payload=payload, timeout=timeout)
            outcome = {
                "call": i + 1, "status": 200,
                "latency_seconds": round(time.monotonic() - started, 3),
                "usage": {
                    name: reply.get("usage", {}).get(name)
                    for name in ("prompt_tokens", "completion_tokens", "total_tokens")
                },
            }
        except urllib.error.HTTPError as exc:
            # Do not print response bodies or headers; provider errors could leak data.
            outcome = {
                "call": i + 1, "status": int(exc.code),
                "latency_seconds": round(time.monotonic() - started, 3),
            }
        except (urllib.error.URLError, TimeoutError) as exc:
            outcome = {
                "call": i + 1, "status": type(exc).__name__,
                "latency_seconds": round(time.monotonic() - started, 3),
            }
        attempts.append(outcome)
        # Stop on authorization/model errors. No unbounded retries.
        if outcome["status"] in (400, 401, 403, 404):
            break
    return {
        "result": "complete",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "groq",
        "model": model,
        "available_model_ids": model_ids,
        "chat_calls_attempted": len(attempts),
        "chat_calls_succeeded": sum(row["status"] == 200 for row in attempts),
        "429_count": sum(row["status"] == 429 for row in attempts),
        "attempts": attempts,
        "caution": "This sample cannot establish exact sustainable rate limits. "
                   "A succeeded call does not imply the model supports tool calling.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--pause", type=float, default=6)
    parser.add_argument("--output", default="data/runs/groq-preflight.json")
    parser.add_argument("--i-understand-this-makes-real-calls", action="store_true")
    args = parser.parse_args()
    if not args.i_understand_this_makes_real_calls:
        parser.error("explicit opt-in flag required")
    config = yaml.safe_load(Path("config/groq.example.yaml").read_text(encoding="utf-8"))
    model = args.model or config["models"]["victim"]
    report = preflight(os.environ.get("GROQ_API_KEY"), model, count=args.count,
                       sleep_seconds=args.pause)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # Printed output has no secret or request/response body.
    print(json.dumps({k: v for k, v in report.items() if k != "attempts"}, indent=2))
    if report["result"] != "complete" or report["chat_calls_succeeded"] == 0:
        raise SystemExit("Preflight did not confirm successful model responses.")


if __name__ == "__main__":
    main()
