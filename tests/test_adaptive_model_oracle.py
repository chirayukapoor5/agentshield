"""Synthetic offline tests for the budgeted proposer and real-checker adapter."""
import json

import pytest

from src.attack.model_proposer import InvalidProposal, ModelAttackerProposer
from src.eval.adaptive_oracle import make_training_oracle


class StubClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []
    def chat(self, role, messages, **kwargs):
        self.calls.append((role, messages, kwargs))
        return {"choices": [{"message": {"content": self.reply}}]}


def candidate(**override):
    value = {"text": "synthetic attacker tool-output candidate",
             "language": "en", "script": "Latn",
             "code_mix_ratio": 0, "strategy": "fixture"}
    value.update(override)
    return json.dumps(value)


def test_model_proposer_parses_bounded_english_candidate():
    client = StubClient(candidate())
    proposer = ModelAttackerProposer(client)
    result = proposer("initial", [], "C3", ["en"])
    assert result["language"] == "en"
    assert len(client.calls) == 1
    assert client.calls[0][0] == "attacker"
    assert client.calls[0][2]["retries"] == 0


def test_model_proposer_is_feedback_dependent_not_given_raw_trace():
    client = StubClient(candidate(language="es", code_mix_ratio=0.25))
    proposer = ModelAttackerProposer(client)
    history = [{
        "attempt": 1, "status": "scored", "success": False,
        "language": "en", "script": "Latn",
        "code_mix_ratio": 0, "candidate_sha256": "a" * 64,
        "visible_defense_output": "PRIVATE DEFENDER RESPONSE MUST NOT LEAK",
    }]
    result = proposer("initial", history, "C4", ["en", "es"])
    assert result["language"] == "es"
    message = client.calls[0][1][1]["content"]
    assert "PRIVATE DEFENDER RESPONSE MUST NOT LEAK" not in message
    assert "candidate_sha256" in message


@pytest.mark.parametrize("reply", [
    "not-json", candidate(language="de"), candidate(code_mix_ratio=float("nan")),
    candidate(text="x" * 4000), candidate(strategy=""),
])
def test_proposer_refuses_invalid_payload(reply):
    with pytest.raises(InvalidProposal):
        ModelAttackerProposer(StubClient(reply))("initial", [], "C3", ["en"])


def test_adaptive_oracle_only_exposes_official_security_boolean(monkeypatch):
    from src.eval import agentdojo_adapter
    monkeypatch.setattr(agentdojo_adapter, "require_agentdojo", lambda: None)
    class Suite:
        def get_user_task_by_id(self, key):
            return key
        def get_injection_task_by_id(self, key):
            return key
        def run_task_with_pipeline(self, **kwargs):
            assert kwargs["injections"] == {"tool_response": "candidate"}
            return True, False
    pair = {"user_task_id": "user", "injection_task_id": "attack",
            "injection_slot": "tool_response", "split": "dev"}
    evaluator = make_training_oracle(Suite(), object(), pair)
    assert evaluator("candidate") == {"success": False}


def test_adaptive_oracle_never_sees_heldout_task():
    with pytest.raises(ValueError, match="dev/tune"):
        make_training_oracle(object(), object(), {"split": "test"})
