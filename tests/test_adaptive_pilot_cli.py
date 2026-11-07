"""Offline CLI gates for the real adaptive search pilot."""
import pytest

from scripts.run_adaptive import available_languages, select_training_pair


def test_adaptive_training_rejects_unreviewed_non_english_languages():
    config = {"languages": [
        {"id": "en", "native_validation_available": True},
        {"id": "es", "native_validation_available": False},
        {"id": "FILL_IN_LANGUAGE_1", "native_validation_available": True},
    ]}
    with pytest.raises(ValueError, match="reviewed non-English"):
        available_languages("C4", config)
    assert available_languages("C3", config) == ["en"]


def test_adaptive_training_accepts_validated_language_set():
    config = {"languages": [
        {"id": "en", "native_validation_available": True},
        {"id": "es", "native_validation_available": True},
    ]}
    assert available_languages("C4", config) == ["en", "es"]


def test_training_pair_selects_only_dev_or_tune():
    dev = {"user_task_id": "u1", "injection_task_id": "i1",
           "injection_slot": "slot", "split": "dev"}
    test = {"user_task_id": "u2", "injection_task_id": "i2",
            "injection_slot": "slot", "split": "test"}
    manifest = {"suite": "workspace", "pairs": [dev, test]}
    assert select_training_pair(manifest, scenario="u1::i1::slot") == dev
    with pytest.raises(ValueError, match="held-out"):
        select_training_pair(manifest, scenario="u2::i2::slot")
    with pytest.raises(ValueError, match="exact"):
        select_training_pair(manifest, scenario="no::such::scenario")
