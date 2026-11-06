"""Paired C3/C4 contrast from validated research JSONL, with honest denominators.

This module analyzes *reported* labels only. It does NOT certify official
AgentDojo execution, ground-truth attack success, or valid translation.
It refuses duplicate comparison keys, split leakage, and silent missing cases.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from research.validate_results import validate
from src.analysis.metrics import paired_bootstrap

KEY_FIELDS = ("scenario_id", "split", "defense_id", "model_id", "seed")
CLUSTER_FIELD = "scenario_id"


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank result line {line_number}")
            try:
                record = validate(json.loads(line), line_number)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid result JSON at line {line_number}") from exc
            if record["trial_id"] in seen_ids:
                raise ValueError(f"duplicate trial_id: {record['trial_id']}")
            seen_ids.add(record["trial_id"])
            records.append(record)
    return records


def paired_report(records: list[dict[str, Any]], *,
                  split: str = "test", samples: int = 2000,
                  seed: int = 20261105) -> dict[str, Any]:
    """Match C3/C4 by exact scenario, split, defense, model and seed.

    Ignore other conditions *by design*. Count unscorable and unmatched cases.
    A scenario ID is the conservative cluster identifier; it may be finer
    than scenario family. No inferential claim is made until family metadata
    is independently checked.
    """
    if split not in {"dev", "tune", "test"}:
        raise ValueError("split must be dev, tune or test")
    if type(samples) is not int or samples < 100:
        raise ValueError("samples must be >= 100")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")

    selected: dict[tuple, dict[str, dict]] = defaultdict(dict)
    scenario_split: dict[str, str] = {}
    per_condition: Counter = Counter()
    for number, record in enumerate(records, 1):
        validate(record, number)
        if record["condition"] not in {"C3", "C4"}:
            continue
        family = record["scenario_id"]
        previous_split = scenario_split.setdefault(family, record["split"])
        if previous_split != record["split"]:
            raise ValueError(f"scenario split leakage: {family}")
        if record["split"] != split:
            continue
        condition = record["condition"]
        per_condition[condition] += 1
        key = tuple(record[field] for field in KEY_FIELDS)
        if condition in selected[key]:
            raise ValueError(f"duplicate C3/C4 comparison cell: {key} / {condition}")
        selected[key][condition] = record

    paired_scored: list[tuple[str, bool, bool]] = []
    dropped = Counter()
    total_matched = 0
    c3_successes = 0
    c4_successes = 0
    c3_scored = 0
    c4_scored = 0
    for key, arms in selected.items():
        if "C3" not in arms or "C4" not in arms:
            dropped["missing_C3" if "C3" not in arms else "missing_C4"] += 1
            continue
        total_matched += 1
        a, b = arms["C3"], arms["C4"]
        c3_scored += int(a["outcome"] == "scored")
        c4_scored += int(b["outcome"] == "scored")
        c3_successes += int(a["success"] is True)
        c4_successes += int(b["success"] is True)
        if a["outcome"] != "scored" or b["outcome"] != "scored":
            dropped[f"not_both_scored:{a['outcome']}:{b['outcome']}"] += 1
            continue
        paired_scored.append((key[0], a["success"], b["success"]))

    estimates = paired_bootstrap(paired_scored, samples=samples, seed=seed)
    # Bounds on marginal success rates across matched attempted trials. A
    # failed or unscorable outcome could be either success or failure.
    sensitivity = {
        "C3": {"lower": c3_successes / total_matched if total_matched else None,
               "upper": (c3_successes + total_matched - c3_scored) / total_matched
               if total_matched else None},
        "C4": {"lower": c4_successes / total_matched if total_matched else None,
               "upper": (c4_successes + total_matched - c4_scored) / total_matched
               if total_matched else None},
    }
    return {
        "data_provenance": "unverified_reported_labels",
        "warning": ("No official checker provenance or language validity verified. "
                    "Scenario ID used as cluster proxy; check scenario families "
                    "before inferential interpretation."),
        "split": split,
        "attempts_by_condition": dict(sorted(per_condition.items())),
        "matched_attempted": total_matched,
        "paired_scored": len(paired_scored),
        "excluded_cells": dict(sorted(dropped.items())),
        "marginal_sensitivity_bounds_all_matched": sensitivity,
        "paired_scored_only_bootstrap": estimates,
        "bootstrap_resamples": samples,
        "bootstrap_seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--split", choices=("dev", "tune", "test"), default="test")
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = paired_report(load_records(args.results), split=args.split,
                               samples=args.samples, seed=args.seed)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"paired analysis refused: {exc}\n")
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
