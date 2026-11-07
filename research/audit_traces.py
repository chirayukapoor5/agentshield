"""Audit declared AgentDojo trial traces before interpreting result labels.

Schema checks do not prove the underlying model execution happened, but they
prevent missing files, checker-type mismatches, altered labels and path escapes
from silently entering a publishable result table.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from research.paired_analysis import load_records

OFFICIAL_CHECKER = "agentdojo.TaskSuite.run_task_with_pipeline"


def _reject_duplicate_keys(pairs):
    """Refuse ambiguous JSON metadata rather than trusting the last duplicate."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON object key")
        obj[key] = value
    return obj



def audit_traces(results: Path) -> dict:
    results = Path(results)
    root = results.parent.resolve()
    records = load_records(results)
    by_condition: dict[str, dict[str, int]] = {}
    failures: list[str] = []
    verified = 0
    for record in records:
        condition = record["condition"]
        group = by_condition.setdefault(condition, {
            "total": 0, "scored": 0, "trace_verified": 0})
        group["total"] += 1
        if record["outcome"] != "scored":
            continue
        group["scored"] += 1
        ref = record["artifact_ref"]
        path = (root / ref).resolve()
        label = record["trial_id"]
        if not path.is_relative_to(root):
            failures.append(f"{label}: trace path escapes results folder")
            continue
        if not path.is_file():
            failures.append(f"{label}: trace file missing")
            continue
        try:
            trace = json.loads(path.read_text(encoding="utf-8"),
                               object_pairs_hook=_reject_duplicate_keys)
        except (OSError, ValueError):
            failures.append(f"{label}: invalid trace JSON")
            continue
        if not isinstance(trace, dict):
            failures.append(f"{label}: trace must be an object")
            continue
        checks = (
            trace.get("trial_id") == label,
            trace.get("checker") == OFFICIAL_CHECKER,
            trace.get("redacted") is True,
            type(trace.get("attack_success")) is bool,
            trace.get("attack_success") is record["success"],
            type(trace.get("user_utility")) is bool,
            isinstance(trace.get("payload_sha256"), str)
            and bool(re.fullmatch(r"[a-f0-9]{64}", trace["payload_sha256"])),
        )
        if not all(checks):
            failures.append(f"{label}: trace/checker/label/hash mismatch")
            continue
        verified += 1
        group["trace_verified"] += 1
    return {
        "status": ("no_trials" if not records else
                   "trace_structures_valid" if not failures else "trace_audit_failed"),
        "rows": len(records), "scored": sum(v["scored"] for v in by_condition.values()),
        "verified_scored_traces": verified, "by_condition": by_condition,
        "failures": failures,
        "caveat": "Checks metadata consistency, not independent provider or checker provenance.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("results", type=Path)
    args = p.parse_args()
    try:
        report = audit_traces(args.results)
    except (OSError, ValueError) as exc:
        p.exit(2, f"trace audit refused: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "trace_structures_valid":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
