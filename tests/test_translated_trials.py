"""C2 translation checks: offline fixtures, never labeled measured ASR."""
import hashlib

import pytest

from src.eval import translated_trials


PAIR = {"user_task_id": "user_task_1", "injection_task_id": "inj_1",
        "injection_slot": "tool_result", "split": "dev"}
ORIGINAL = "Synthetic English injection fixture only"


def translation(**overrides):
    data = {
        "id": "fixture1", "scenario_id": translated_trials.scenario_id(PAIR),
        "lang": "es", "source_sha256": hashlib.sha256(ORIGINAL.encode()).hexdigest(),
        "text": "Una cadena sintética de prueba",
        "validated_by_me": True, "needs_native_check": False,
    }
    data.update(overrides)
    return data


def test_unreviewed_translations_are_refused():
    for patch in [
        {"validated_by_me": False}, {"needs_native_check": True},
        {"source_sha256": "0" * 64},
        {"lang": "de"}, {"scenario_id": "different"}, {"text": ""},
    ]:
        with pytest.raises(ValueError):
            translated_trials.select_verified_translation(
                translation(**patch), scenario=translated_trials.scenario_id(PAIR),
                language="es", english_payload=ORIGINAL)


def test_c2_official_checker_contract_with_dummy_suite(monkeypatch):
    from src.eval import agentdojo_adapter
    monkeypatch.setattr(agentdojo_adapter, "require_agentdojo", lambda: None)

    class Suite:
        name = "workspace"
        def get_user_task_by_id(self, identifier):
            return identifier
        def get_injection_task_by_id(self, identifier):
            return identifier
        def run_task_with_pipeline(self, **kwargs):
            assert kwargs["injections"]["tool_result"] == translation()["text"]
            return True, False

    data = translated_trials.run_translated_pair(
        Suite(), object(), PAIR, english_payload=ORIGINAL,
        translation=translation(), language="es", script="Latn",
        victim_model_id="fixture-only", defense_id="none", seed=11)
    record = data["record"]
    assert record["condition"] == "C2"
    assert record["language"] == "es"
    assert record["outcome"] == "scored"
    assert record["success"] is False
    assert data["trace"]["user_utility"] is True
    assert ORIGINAL not in str(data)
    assert translation()["text"] not in str(data)


def test_c2_rejects_unfrozen_split_before_agentdojo_import():
    with pytest.raises(ValueError, match="split"):
        translated_trials.run_translated_pair(
            object(), object(), {**PAIR, "split": None},
            english_payload=ORIGINAL, translation=translation(),
            language="es", script="Latn", victim_model_id="fixture",
            defense_id="none", seed=1)
