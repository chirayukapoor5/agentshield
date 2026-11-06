"""Verify research trace schema without AgentDojo, models, or network."""
import json
import sys
import types

import pytest

from research.validate_results import summarize
from src.eval import trials


def test_official_trial_mapping_matches_results_validator(monkeypatch, tmp_path):
    monkeypatch.setattr(trials, "require_agentdojo", lambda: None)
    agentdojo = types.ModuleType("agentdojo")
    attacks = types.ModuleType("agentdojo.attacks")
    baseline = types.ModuleType("agentdojo.attacks.baseline_attacks")
    class DirectAttack:
        def __init__(self, *_):
            pass
        def attack(self, user, injection):
            return {"mock_tool_output": "Synthetic untrusted text"}
    baseline.DirectAttack = DirectAttack
    monkeypatch.setitem(sys.modules, "agentdojo", agentdojo)
    monkeypatch.setitem(sys.modules, "agentdojo.attacks", attacks)
    monkeypatch.setitem(sys.modules, "agentdojo.attacks.baseline_attacks", baseline)

    class Suite:
        name = "workspace"
        def get_user_task_by_id(self, identifier):
            return identifier
        def get_injection_task_by_id(self, identifier):
            return identifier
        def run_task_with_pipeline(self, **kwargs):
            assert kwargs["injections"]["mock_tool_output"] == "Synthetic untrusted text"
            return True, False

    pair = {"user_task_id": "u1", "injection_task_id": "i1",
            "injection_slot": "mock_tool_output", "split": "dev"}
    result = trials.run_english_static_pair(
        Suite(), object(), pair, victim_model_id="mock-victim",
        attacker_model_id="mock-attacker", translator_model_id="mock-translator",
        seed=11, defense_id="none", api_parameters={"temperature": 0})

    path = tmp_path / "official.jsonl"
    assert trials.append_trial(path, result)
    assert not trials.append_trial(path, result)
    analysis = summarize(path)
    assert analysis["trials"] == 1
    assert analysis["groups"][0]["successes"] == 0
    assert analysis["groups"][0]["scored"] == 1

    trace_path = path.parent / result["record"]["artifact_ref"]
    trace = json.loads(trace_path.read_text())
    assert trace["user_utility"] is True
    assert trace["attack_success"] is False
    assert trace["redacted"] is True
    assert "Synthetic untrusted text" not in trace_path.read_text()


def test_official_trial_refuses_missing_family_split(monkeypatch):
    monkeypatch.setattr(trials, "require_agentdojo", lambda: None)
    with pytest.raises(ValueError, match="split"):
        trials.run_english_static_pair(
            object(), object(), {"user_task_id": "u", "injection_task_id": "i",
                                 "injection_slot": "x"},
            victim_model_id="v", attacker_model_id="a", translator_model_id="t",
            seed=0, defense_id="none", api_parameters={})


def test_append_rejects_nonredacted_trace(tmp_path):
    sample = {"record": {
        "trial_id": "case-1", "scenario_id": "u::i::x", "split": "dev",
        "condition": "C1", "language": "en", "script": "Latn", "code_mixed": False,
        "defense_id": "none", "model_id": "model", "seed": 1, "attacker_queries": 0,
        "outcome": "scored", "success": False, "artifact_ref": "traces/case-1.json"},
        "trace": {"trial_id": "case-1", "redacted": False}}
    with pytest.raises(ValueError):
        trials.append_trial(tmp_path / "results.jsonl", sample)
