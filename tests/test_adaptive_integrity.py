"""Adaptive search integrity tests. All oracles are synthetic and offline."""
import json

import pytest

from src.attack.search import run_search


def propose(initial, history, condition, languages):
    return {"text": initial + str(len(history)), "language": "en",
            "script": "Latn", "code_mix_ratio": 0, "strategy": "fixture"}


def run(tmp_path, **kwargs):
    defaults = dict(
        propose=propose, evaluate=lambda _: {"success": False,
                                             "visible_defense_output": "SENSITIVE RAW TRACE"},
        initial="fixture", condition="C3", languages=("en",), budget=2,
        run_id="dev:case1:none:seed11",
        log_path=tmp_path / "attempts.jsonl")
    defaults.update(kwargs)
    return run_search(**defaults)


def test_log_does_not_store_raw_defender_output(tmp_path):
    outcome = run(tmp_path)
    assert outcome["attempts"] == 2
    serialized = (tmp_path / "attempts.jsonl").read_text()
    assert "SENSITIVE RAW TRACE" not in serialized
    assert "fixture0" not in serialized
    assert all(row["status"] == "scored" for row in outcome["history"])


@pytest.mark.parametrize("change", [
    {"initial": "other"}, {"run_id": "dev:other:seed11"},
    {"budget": 3},
])
def test_resume_rejects_different_experiment(tmp_path, change):
    run(tmp_path)
    with pytest.raises(ValueError, match="different experiment"):
        run(tmp_path, **change)


def test_oracle_error_is_recorded_and_resume_refused(tmp_path):
    def broken(_):
        raise OSError("provider is offline")
    with pytest.raises(OSError):
        run(tmp_path, evaluate=broken)
    rows = [json.loads(x) for x in
            (tmp_path / "attempts.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["status"] == "unscorable"
    assert rows[0]["success"] is None
    with pytest.raises(RuntimeError, match="manual review"):
        run(tmp_path)


def test_resume_does_not_query_again_after_success(tmp_path):
    counter = []
    first = run(tmp_path, evaluate=lambda _: {"success": True})
    second = run(tmp_path, evaluate=lambda _: counter.append(1))
    assert first["attempts"] == second["attempts"] == 1
    assert counter == []


def test_nan_code_mix_is_rejected_without_feedback_call(tmp_path):
    counter = []
    with pytest.raises(ValueError, match="code-mix"):
        run(tmp_path, propose=lambda *_: {
            "text": "x", "language": "en", "script": "Latn",
            "code_mix_ratio": float("nan"), "strategy": "test"},
            evaluate=lambda _: counter.append(1))
    assert counter == []


def test_existing_log_cannot_be_overwritten_without_resume(tmp_path):
    run(tmp_path)
    with pytest.raises(ValueError, match="overwrite"):
        run(tmp_path, resume=False)
