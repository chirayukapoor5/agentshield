"""Offline tests for C2 preparation: rejected input cannot reach defender."""
import hashlib

import pytest

from scripts.run_translated import prepare_cases
from src.eval.translated_trials import scenario_id


PAIR = {"user_task_id": "user_task_1", "injection_task_id": "injection_task_1",
        "injection_slot": "tool_slot", "split": "dev"}
TEXT = "Original synthetic English attack reference"
HASH = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()


def item(**values):
    base = {"id": "translation-1", "scenario_id": scenario_id(PAIR),
            "lang": "es", "source_sha256": HASH,
            "text": "Texto traducido sintético",
            "validated_by_me": True, "needs_native_check": False}
    base.update(values)
    return base


def test_all_verified_items_are_prepared():
    prepared = prepare_cases([PAIR], {"items": [item()]}, split="dev",
                             language="es", reference_payload=lambda _: TEXT)
    assert len(prepared) == 1
    assert prepared[0][2]["source_sha256"] == HASH


def test_missing_unreviewed_or_wrong_hash_is_rejected():
    for translations in [
        {"items": []},
        {"items": [item(validated_by_me=False)]},
        {"items": [item(source_sha256="e" * 64)]},
        {"items": [item(needs_native_check=True)]},
    ]:
        with pytest.raises(ValueError):
            prepare_cases([PAIR], translations, split="dev", language="es",
                          reference_payload=lambda _: TEXT)


def test_duplicate_translation_scenario_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        prepare_cases([PAIR], {"items": [item(), item(id="translation-2")]},
                      split="dev", language="es", reference_payload=lambda _: TEXT)


def test_empty_split_does_not_use_wrong_partition():
    with pytest.raises(ValueError, match="no scenario"):
        prepare_cases([PAIR], {"items": [item()]}, split="test", language="es",
                      reference_payload=lambda _: TEXT)


def test_no_reference_payload_accepted_as_verified():
    with pytest.raises(ValueError, match="payload"):
        prepare_cases([PAIR], {"items": [item()]}, split="dev", language="es",
                      reference_payload=lambda _: "")
