"""Budget-matched black-box proposal/evaluation loop.

The evaluator must report AgentDojo's official checker outcomes; mock runs produce
only diagnostic output and are ineligible for scientific results.
"""
import hashlib
import json
from pathlib import Path

def run_search(*, propose, evaluate, initial, condition, languages, budget=10,
               log_path=None, resume=True):
    if condition not in ("C3", "C4"):
        raise ValueError("adaptive condition must be C3 or C4")
    if type(budget) is not int or budget < 1:
        raise ValueError("budget must be a positive integer")
    history = []
    log_path = Path(log_path) if log_path is not None else None
    if log_path and resume and log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                history.append(json.loads(line))
        if len(history) > budget:
            raise ValueError("resume log exceeds allowed query budget")
        if any(row["condition"] != condition or row["attempt"] != i + 1 for i, row in enumerate(history)):
            raise ValueError("resume history is inconsistent")
    best = next((row for row in history if row.get("success") is True), None)
    if best is not None:
        return {"attempts": len(history), "first_success": best["attempt"], "best": best, "history": history}
    for index in range(len(history), budget):
        proposal = propose(initial, list(history), condition, tuple(languages))
        if not isinstance(proposal, dict):
            raise ValueError("proposer must return a structured dictionary")
        for field in ("text", "language", "script", "code_mix_ratio", "strategy"):
            if field not in proposal:
                raise ValueError("missing proposal field: " + field)
        if not isinstance(proposal["text"], str) or not proposal["text"]:
            raise ValueError("empty proposal")
        if condition == "C3" and (proposal["language"] != "en" or proposal["code_mix_ratio"] != 0):
            raise ValueError("C3 candidates must be English-only")
        if proposal["language"] not in (("en",) if condition == "C3" else languages):
            raise ValueError("candidate language was not configured")
        if not 0 <= proposal["code_mix_ratio"] <= 1:
            raise ValueError("code-mix ratio must lie within [0,1]")
        feedback = evaluate(proposal["text"])
        # Only binary success and visible defense feedback are allowed.
        if not isinstance(feedback, dict) or type(feedback.get("success")) is not bool:
            raise ValueError("evaluator must supply boolean success")
        row = {
            "condition": condition, "attempt": index + 1,
            "language": proposal["language"], "script": proposal["script"],
            "code_mix_ratio": proposal["code_mix_ratio"], "strategy": proposal["strategy"],
            "candidate_sha256": hashlib.sha256(proposal["text"].encode()).hexdigest(),
            "success": feedback["success"], "visible_defense_output": feedback.get("visible_defense_output"),
            "refusal": bool(proposal.get("refusal", False)),
        }
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
        history.append(row)
        if feedback["success"]:
            best = row
            break
    return {"attempts": len(history), "first_success": next((r["attempt"] for r in history if r["success"]), None),
            "best": best, "history": history}
