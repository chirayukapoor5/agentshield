"""Budgeted black-box candidate selection for C3/C4 research.

This is an orchestration component. Real feedback must come from official
AgentDojo security checkers; mock feedback MUST NOT become research ASR.
The log intentionally stores hashes and categorical labels, never raw prompts,
defender responses, or injection text.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _fingerprint(initial, condition, languages, budget, run_id):
    frozen = {"initial": initial, "condition": condition,
              "languages": list(languages), "budget": budget, "run_id": run_id}
    return hashlib.sha256(json.dumps(frozen, sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _append(path, row):
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()


def run_search(*, propose, evaluate, initial, condition, languages, budget=10,
               log_path=None, resume=True, run_id="local-unverified"):
    """Select a candidate under a fixed query cap, with resumption protection.

    The candidate proposer may use a model; its calls must ALSO be accounted in
    the provider's persistent request ledger. A feedback-oracle failure consumes
    a query and halts. The run cannot silently resume across different initial
    payloads, language sets or scenario IDs (supply a unique run_id per case).
    """
    if condition not in ("C3", "C4"):
        raise ValueError("adaptive condition must be C3 or C4")
    if type(budget) is not int or budget < 1:
        raise ValueError("budget must be a positive integer")
    if not isinstance(initial, str) or not initial:
        raise ValueError("initial attack text must be nonempty")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must identify the scenario and defense")
    if not isinstance(languages, (list, tuple)) or not languages or any(
            not isinstance(v, str) or not v for v in languages):
        raise ValueError("languages must be nonempty strings")
    if condition == "C3" and tuple(languages) != ("en",):
        raise ValueError("C3 requires English-only language settings")
    if not callable(propose) or not callable(evaluate):
        raise ValueError("proposal and oracle callbacks required")

    languages = tuple(languages)
    fingerprint = _fingerprint(initial, condition, languages, budget, run_id)
    history = []
    log_path = Path(log_path) if log_path is not None else None
    if log_path is not None and not resume and log_path.exists():
        raise ValueError("resume=False refuses to overwrite an existing log")
    if log_path and resume and log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                raise ValueError("blank adaptive-search log line")
            history.append(json.loads(line))
        if len(history) > budget:
            raise ValueError("resume log exceeds allowed query budget")
        if any(row.get("fingerprint") != fingerprint or
               row.get("condition") != condition or
               row.get("attempt") != i + 1 for i, row in enumerate(history)):
            raise ValueError("resume history belongs to a different experiment")
        if any(row.get("status") != "scored" for row in history):
            raise RuntimeError("unscorable oracle attempts require manual review")
    best = next((row for row in history if row.get("success") is True), None)
    if best is not None:
        return {"attempts": len(history), "first_success": best["attempt"],
                "best": best, "history": history}

    for index in range(len(history), budget):
        proposal = propose(initial, list(history), condition, languages)
        if not isinstance(proposal, dict):
            raise ValueError("proposer must return a structured dictionary")
        for field in ("text", "language", "script", "code_mix_ratio", "strategy"):
            if field not in proposal:
                raise ValueError("missing proposal field: " + field)
        if not isinstance(proposal["text"], str) or not proposal["text"]:
            raise ValueError("empty proposal")
        ratio = proposal["code_mix_ratio"]
        if (type(ratio) not in (int, float) or not math.isfinite(ratio)
                or not 0 <= ratio <= 1):
            raise ValueError("code-mix ratio must lie within [0,1]")
        if condition == "C3" and (proposal["language"] != "en" or ratio != 0):
            raise ValueError("C3 candidates must be English-only")
        if proposal["language"] not in (("en",) if condition == "C3" else languages):
            raise ValueError("candidate language was not configured")
        if any(not isinstance(proposal[name], str) or
               not proposal[name] for name in ("script", "strategy")):
            raise ValueError("strategy and script must be nonempty strings")
        row = {
            "condition": condition, "fingerprint": fingerprint,
            "attempt": index + 1, "language": proposal["language"],
            "script": proposal["script"], "code_mix_ratio": ratio,
            "strategy": proposal["strategy"],
            "candidate_sha256": hashlib.sha256(proposal["text"].encode()).hexdigest(),
        }
        try:
            feedback = evaluate(proposal["text"])
            if not isinstance(feedback, dict) or type(feedback.get("success")) is not bool:
                raise ValueError("oracle must supply an official boolean outcome")
        except Exception:
            _append(log_path, {**row, "status": "unscorable", "success": None})
            raise
        # No raw visible_defense_output: it could contain hostile instructions,
        # secrets or personal data; a categorical success label is sufficient.
        row.update({"status": "scored", "success": feedback["success"]})
        _append(log_path, row)
        history.append(row)
        if row["success"]:
            best = row
            break
    return {
        "attempts": len(history),
        "first_success": next((r["attempt"] for r in history if r["success"]), None),
        "best": best, "history": history,
    }
