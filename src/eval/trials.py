"""Official AgentDojo static English trials with validator-compatible metadata.

Security/utility labels come exclusively from AgentDojo's official checkers.
Outputs contain no raw payload, secret, model message or tool arguments.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from src.eval.agentdojo_adapter import require_agentdojo

CHECKER = "agentdojo.TaskSuite.run_task_with_pipeline"


def run_english_static_pair(suite, pipeline, pair, *, attack=None,
                            victim_model_id, attacker_model_id,
                            translator_model_id, seed, defense_id,
                            api_parameters, suite_version="v1.2.2"):
    require_agentdojo()
    from agentdojo.attacks.baseline_attacks import DirectAttack

    if pair.get("split") not in ("dev", "tune", "test"):
        raise ValueError("manifest pair must have a frozen scenario-family split")
    if attack is None:
        attack = DirectAttack(suite, pipeline)
    user = suite.get_user_task_by_id(pair["user_task_id"])
    injection = suite.get_injection_task_by_id(pair["injection_task_id"])
    payloads = attack.attack(user, injection)
    slot = pair["injection_slot"]
    if slot not in payloads:
        raise ValueError("selected lower-trust insertion slot absent in attack payloads")
    payload = payloads[slot]
    if not isinstance(payload, str):
        raise ValueError("AgentDojo attack payload must be string")
    utility, security = suite.run_task_with_pipeline(
        agent_pipeline=pipeline, user_task=user, injection_task=injection,
        injections={slot: payload}, verbose=False)
    if type(utility) is not bool or type(security) is not bool:
        raise ValueError("AgentDojo official checkers returned non-booleans")

    trial_key = json.dumps({"pair": pair, "seed": seed, "defense": defense_id,
                            "model": victim_model_id, "condition": "C1"},
                           sort_keys=True)
    trial_id = hashlib.sha256(trial_key.encode()).hexdigest()[:24]
    scenario = "::".join((pair["user_task_id"], pair["injection_task_id"], slot))
    record = {
        "trial_id": trial_id, "scenario_id": scenario, "split": pair["split"],
        "condition": "C1", "language": "en", "script": "Latn",
        "code_mixed": False, "defense_id": defense_id,
        "model_id": victim_model_id, "seed": seed, "attacker_queries": 0,
        "outcome": "scored", "success": security,
        "artifact_ref": "traces/" + trial_id + ".json",
    }
    trace = {
        "trial_id": trial_id, "checker": CHECKER,
        "checker_version": suite_version, "suite": suite.name,
        "user_utility": utility, "attack_success": security,
        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "attack_template": "AgentDojo DirectAttack",
        "victim_model_id": victim_model_id, "attacker_model_id": attacker_model_id,
        "translator_model_id": translator_model_id, "defense_id": defense_id,
        "seed": seed, "created_utc": datetime.now(timezone.utc).isoformat(),
        "api_parameters": api_parameters,
        "redacted": True,
        "note": "Official checker booleans. No raw tool trace or payload included.",
    }
    return {"record": record, "trace": trace}


def append_trial(path, trial):
    """Write redacted trace and matching JSONL row; skip existing trial IDs.

    The trace is written first. A retry on a crashed run can safely fill the
    missing JSONL row. This is append-only metadata, not independently verified.
    """
    if not isinstance(trial, dict) or set(trial) != {"record", "trace"}:
        raise ValueError("expected official trial record and redacted trace")
    record, trace = trial["record"], trial["trace"]
    # Local validation is deliberately the same schema used for public results.
    from research.validate_results import validate
    validate(record, 1)
    if trace.get("trial_id") != record["trial_id"] or not trace.get("redacted"):
        raise ValueError("redacted trace must match trial ID")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if json.loads(line)["trial_id"] == record["trial_id"]:
                return False
    trace_path = target.parent / record["artifact_ref"]
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(trace, ensure_ascii=False,
                                    sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
    return True
