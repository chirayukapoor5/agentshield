"""C2 translated static-injection runner using official AgentDojo checkers.

Translations are *inputs*, never synthesized by this script. Each C2 candidate
must match the SHA-256 of the C1 reference injection and be human-validated.
Model execution is opt-in and bound by the existing src.llm.Client ledger.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from research.validate_results import validate


def scenario_id(pair):
    return "::".join((pair["user_task_id"], pair["injection_task_id"],
                      pair["injection_slot"]))


def select_verified_translation(item, *, scenario, language, english_payload):
    """Refuse unreviewed, mismatched or recycled translations."""
    if not isinstance(english_payload, str) or not english_payload:
        raise ValueError("nonempty C1 payload required")
    if not isinstance(item, dict):
        raise ValueError("translation must be an object")
    if item.get("scenario_id") != scenario or item.get("lang") != language:
        raise ValueError("translation scenario or language mismatch")
    source_digest = hashlib.sha256(english_payload.encode("utf-8")).hexdigest()
    if item.get("source_sha256") != source_digest:
        raise ValueError("translated injection does not match frozen English payload")
    if item.get("validated_by_me") is not True or item.get("needs_native_check") is not False:
        raise ValueError("translation requires recorded human validation")
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("translated injection must be nonempty")
    if not isinstance(item.get("lang"), str) or item["lang"] == "en":
        raise ValueError("C2 must use a non-English language")
    return text


def run_translated_pair(suite, pipeline, pair, *, english_payload, translation,
                        language, script, victim_model_id, defense_id, seed,
                        suite_version="v1.2.2"):
    """Run the official checkers, with no alternative LLM-based success judge."""
    from src.eval.agentdojo_adapter import require_agentdojo
    if pair.get("split") not in {"dev", "tune", "test"}:
        raise ValueError("pair split must be fixed before evaluation")
    if not isinstance(script, str) or not script:
        raise ValueError("translation script required")
    scenario = scenario_id(pair)
    injection_text = select_verified_translation(
        translation, scenario=scenario, language=language,
        english_payload=english_payload)
    require_agentdojo()
    user = suite.get_user_task_by_id(pair["user_task_id"])
    injection = suite.get_injection_task_by_id(pair["injection_task_id"])
    utility, security = suite.run_task_with_pipeline(
        agent_pipeline=pipeline, user_task=user, injection_task=injection,
        injections={pair["injection_slot"]: injection_text}, verbose=False)
    if type(utility) is not bool or type(security) is not bool:
        raise ValueError("AgentDojo official checker did not return booleans")
    key = json.dumps({"scenario": scenario, "split": pair["split"],
                      "language": language, "model": victim_model_id,
                      "defense": defense_id, "seed": seed, "condition": "C2"},
                     sort_keys=True)
    trial_id = hashlib.sha256(key.encode()).hexdigest()[:24]
    record = {
        "trial_id": trial_id, "scenario_id": scenario, "split": pair["split"],
        "condition": "C2", "language": language, "script": script,
        "code_mixed": False, "defense_id": defense_id,
        "model_id": victim_model_id, "seed": seed, "attacker_queries": 0,
        "outcome": "scored", "success": security,
        "artifact_ref": "traces/" + trial_id + ".json",
    }
    validate(record, 1)
    trace = {
        "trial_id": trial_id, "checker": "agentdojo.TaskSuite.run_task_with_pipeline",
        "checker_version": suite_version, "suite": suite.name,
        "attack_success": security, "user_utility": utility,
        "source_sha256": hashlib.sha256(english_payload.encode()).hexdigest(),
        "payload_sha256": hashlib.sha256(injection_text.encode()).hexdigest(),
        "validated_by_me": True, "language": language,
        "translation_id": translation.get("id"), "redacted": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    return {"record": record, "trace": trace}
