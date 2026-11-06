"""Strict comparison tests use fabricated fixture labels, never benchmark ASR."""
import json

import pytest

from research.paired_analysis import load_records, paired_report


def record(condition="C3", *, trial="a", scenario="s1", split="test",
           outcome="scored", success=False, seed=11):
    return {
        "trial_id": trial, "scenario_id": scenario, "split": split,
        "condition": condition, "language": "en" if condition == "C3" else "es",
        "script": "Latn", "code_mixed": False, "defense_id": "none",
        "model_id": "fixture-only", "seed": seed,
        "attacker_queries": 10, "outcome": outcome, "success": success,
        "artifact_ref": "traces/" + trial + ".json",
    }


def test_matched_scored_comparison_and_determinism():
    rows = [record("C3", trial="a", success=False),
            record("C4", trial="b", success=True),
            record("C3", trial="c", scenario="s2", success=True),
            record("C4", trial="d", scenario="s2", success=True)]
    first = paired_report(rows, samples=100, seed=3)
    second = paired_report(list(reversed(rows)), samples=100, seed=3)
    assert first == second
    assert first["matched_attempted"] == 2
    assert first["paired_scored"] == 2
    assert first["paired_scored_only_bootstrap"]["difference_c4_minus_c3"] == 0.5
    assert first["data_provenance"] == "unverified_reported_labels"


def test_missing_and_unscorable_cases_are_reported():
    rows = [record("C3", trial="a", success=False),
            record("C4", trial="b", outcome="timeout", success=None),
            record("C3", trial="c", scenario="s2", success=True)]
    result = paired_report(rows, samples=100)
    assert result["matched_attempted"] == 1
    assert result["paired_scored"] == 0
    assert result["excluded_cells"]["missing_C4"] == 1
    assert result["excluded_cells"]["not_both_scored:scored:timeout"] == 1
    assert result["marginal_sensitivity_bounds_all_matched"]["C4"] == {
        "lower": 0, "upper": 1}


def test_duplicate_pair_cell_refused():
    rows = [record("C3", trial="a"), record("C3", trial="b")]
    with pytest.raises(ValueError, match="duplicate"):
        paired_report(rows, samples=100)


def test_leakage_across_splits_refused():
    rows = [record("C3", trial="a", split="test"),
            record("C4", trial="b", split="dev")]
    with pytest.raises(ValueError, match="leakage"):
        paired_report(rows, samples=100)


def test_invalid_trial_refused():
    with pytest.raises(ValueError, match="attacker_queries"):
        paired_report([record("C3", trial="a", success=False,
                              seed=11) | {"attacker_queries": -1}], samples=100)


def test_load_records_rejects_duplicate_trial_ids(tmp_path):
    path = tmp_path / "results.jsonl"
    row = record("C3", trial="a")
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="duplicate trial_id"):
        load_records(path)


def test_no_scored_pairs_never_fabricates_estimate():
    result = paired_report([], samples=100)
    assert result["paired_scored_only_bootstrap"] is None
    assert result["matched_attempted"] == 0
    assert result["marginal_sensitivity_bounds_all_matched"]["C3"]["lower"] is None


def test_only_requested_split_included():
    rows = [record("C3", trial="a", split="dev"),
            record("C4", trial="b", split="dev")]
    result = paired_report(rows, split="test", samples=100)
    assert result["matched_attempted"] == 0


def test_same_user_task_family_cannot_cross_splits():
    rows = [record("C3", trial="a", scenario="task_7::attack_1::slot",
                   split="dev"),
            record("C4", trial="b", scenario="task_7::attack_2::slot",
                   split="test")]
    with pytest.raises(ValueError, match="leakage"):
        paired_report(rows, samples=100)


def test_cluster_count_is_user_task_family_not_unique_injection_slot():
    rows = [
        record("C3", trial="a", scenario="task_7::attack_1::slot", success=False),
        record("C4", trial="b", scenario="task_7::attack_1::slot", success=True),
        record("C3", trial="c", scenario="task_7::attack_2::slot", success=True),
        record("C4", trial="d", scenario="task_7::attack_2::slot", success=True),
    ]
    result = paired_report(rows, samples=100)
    assert result["paired_scored"] == 2
    assert result["paired_scored_only_bootstrap"]["n_families"] == 1
