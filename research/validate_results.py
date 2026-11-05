"""Validate AgentShield research JSONL metadata and summarize *reported* outcomes.

This does not execute a defender, verify trial traces, or adjudicate success.
Run: python research/validate_results.py path/to/results.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

FIELDS = {
    "trial_id", "scenario_id", "split", "condition", "language",
    "script", "code_mixed", "defense_id", "model_id", "seed",
    "attacker_queries", "outcome", "success", "artifact_ref",
}
CONDITIONS = {"C1", "C2", "C3", "C4", "BENIGN"}
SPLITS = {"dev", "tune", "test"}
OUTCOMES = {"scored", "invalid", "timeout", "tool_error", "unscorable"}


def validate(record: object, line: int) -> dict:
    if not isinstance(record, dict):
        raise ValueError(f"line {line}: trial must be a JSON object")
    missing, extra = FIELDS - record.keys(), record.keys() - FIELDS
    if missing or extra:
        raise ValueError(f"line {line}: missing={sorted(missing)} unknown={sorted(extra)}")
    for key in ("trial_id", "scenario_id", "language", "script", "defense_id", "model_id", "artifact_ref"):
        value = record[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"line {line}: {key} must be a nonempty string")
    if record["split"] not in SPLITS or record["condition"] not in CONDITIONS:
        raise ValueError(f"line {line}: invalid split or condition")
    if record["outcome"] not in OUTCOMES:
        raise ValueError(f"line {line}: invalid outcome")
    if type(record["code_mixed"]) is not bool:
        raise ValueError(f"line {line}: code_mixed must be boolean")
    if type(record["seed"]) is not int or record["seed"] < 0:
        raise ValueError(f"line {line}: seed must be a nonnegative integer")
    if type(record["attacker_queries"]) is not int or record["attacker_queries"] < 0:
        raise ValueError(f"line {line}: attacker_queries must be a nonnegative integer")
    if record["condition"] in {"C1", "C2", "BENIGN"} and record["attacker_queries"] != 0:
        raise ValueError(f"line {line}: static and benign conditions cannot use oracle queries")
    if record["condition"] == "C1" and (record["language"] != "en" or record["code_mixed"]):
        raise ValueError(f"line {line}: C1 requires English and no code mixing")
    if record["condition"] == "C3" and (record["language"] != "en" or record["code_mixed"]):
        raise ValueError(f"line {line}: C3 requires English and no code mixing")
    if record["condition"] == "BENIGN" and record["code_mixed"]:
        raise ValueError(f"line {line}: benign baseline cannot be code-mixed")
    if record["outcome"] == "scored":
        if type(record["success"]) is not bool:
            raise ValueError(f"line {line}: scored trials require boolean success")
    elif record["success"] is not None:
        raise ValueError(f"line {line}: non-scored trials require null success")
    if Path(record["artifact_ref"]).is_absolute() or ".." in Path(record["artifact_ref"]).parts:
        raise ValueError(f"line {line}: artifact_ref must be relative without parent traversal")
    return record


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = successes / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, center - radius), min(1.0, center + radius)


def summarize(path: Path) -> dict:
    seen: set[str] = set()
    groups: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"total": 0, "scored": 0, "successes": 0, "outcomes": defaultdict(int)}
    )
    with path.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            if not raw.strip():
                raise ValueError(f"line {lineno}: blank lines are not allowed")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {lineno}: invalid JSON: {exc.msg}") from exc
            rec = validate(parsed, lineno)
            if rec["trial_id"] in seen:
                raise ValueError(f"line {lineno}: duplicate trial_id {rec['trial_id']!r}")
            seen.add(rec["trial_id"])
            key = rec["split"], rec["condition"], rec["language"]
            group = groups[key]
            group["total"] += 1
            group["outcomes"][rec["outcome"]] += 1
            if rec["outcome"] == "scored":
                group["scored"] += 1
                group["successes"] += int(rec["success"])
    rows = []
    for (split, condition, language), g in sorted(groups.items()):
        interval = wilson(g["successes"], g["scored"])
        rows.append({
            "split": split, "condition": condition, "language": language,
            "total": g["total"], "scored": g["scored"],
            "successes": g["successes"], "outcomes": dict(sorted(g["outcomes"].items())),
            "success_rate_scored_only": g["successes"] / g["scored"] if g["scored"] else None,
            "wilson_95_scored_only": list(interval) if interval is not None else None,
        })
    return {"note": "Descriptive summary of unverified reported labels; non-scored trials excluded only from the displayed scored-only rate.", "trials": len(seen), "groups": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args()
    try:
        report = summarize(args.jsonl)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"validation error: {exc}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
