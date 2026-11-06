"""Synthetic trace-auditor fixtures; not live AgentDojo evidence."""
import hashlib
import json

from research.audit_traces import audit_traces


def make_run(tmp_path, *, trace_updates=None, path="traces/fixture.json"):
    row = {
        "trial_id": "fixture", "scenario_id": "user::injection::slot",
        "split": "dev", "condition": "C1", "language": "en",
        "script": "Latn", "code_mixed": False, "defense_id": "none",
        "model_id": "fixture-model", "seed": 11, "attacker_queries": 0,
        "outcome": "scored", "success": False, "artifact_ref": path,
    }
    trace = {
        "trial_id": "fixture",
        "checker": "agentdojo.TaskSuite.run_task_with_pipeline",
        "redacted": True, "attack_success": False,
        "user_utility": True, "payload_sha256": hashlib.sha256(b"test").hexdigest(),
    }
    trace.update(trace_updates or {})
    target = tmp_path / "results.jsonl"
    target.write_text(json.dumps(row) + "\n")
    trace_file = tmp_path / path
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    trace_file.write_text(json.dumps(trace))
    return target


def test_consistent_trace_accepted(tmp_path):
    report = audit_traces(make_run(tmp_path))
    assert report["status"] == "trace_structures_valid"
    assert report["verified_scored_traces"] == 1


def test_checker_mismatch_or_result_tampering_refused(tmp_path):
    for delta in [
        {"checker": "unverified-llm-judge"},
        {"attack_success": True},
        {"user_utility": "yes"},
        {"payload_sha256": "NOT_A_HASH"},
        {"redacted": False},
    ]:
        path = make_run(tmp_path, trace_updates=delta)
        report = audit_traces(path)
        assert report["status"] == "trace_audit_failed"
        assert report["verified_scored_traces"] == 0


def test_missing_trace_reported_not_silently_ignored(tmp_path):
    path = make_run(tmp_path)
    (tmp_path / "traces" / "fixture.json").unlink()
    report = audit_traces(path)
    assert report["status"] == "trace_audit_failed"
    assert report["failures"] == ["fixture: trace file missing"]
