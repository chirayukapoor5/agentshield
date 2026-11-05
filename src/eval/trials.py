"""Official static English trials; no alternate security or utility scorer."""
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
    if attack is None:
        attack=DirectAttack(suite,pipeline)
    user=suite.get_user_task_by_id(pair["user_task_id"])
    injection=suite.get_injection_task_by_id(pair["injection_task_id"])
    payloads=attack.attack(user,injection)
    slot=pair["injection_slot"]
    if slot not in payloads:
        raise ValueError("chosen lower-trust injection slot was not produced by AgentDojo attack")
    payload=payloads[slot]
    utility,security=suite.run_task_with_pipeline(
        agent_pipeline=pipeline,user_task=user,injection_task=injection,
        injections={slot:payload},verbose=False)
    if type(utility) is not bool or type(security) is not bool:
        raise ValueError("AgentDojo official checker returned non-booleans")
    trial_key=json.dumps({"pair":pair,"seed":seed,"defense":defense_id,
                         "model":victim_model_id,"condition":"C1"},sort_keys=True)
    return {"trial_id":hashlib.sha256(trial_key.encode()).hexdigest()[:24],
            "scenario_id":pair["user_task_id"]+"::"+pair["injection_task_id"]+"::"+slot,
            "condition":"C1","language":"en","script":"Latn","code_mixed":False,
            "validated_by_me":True,"classifier_coverage_status":"not_applicable",
            "seed":seed,"defense_id":defense_id,"model_id":victim_model_id,
            "attacker_model_id":attacker_model_id,"translator_model_id":translator_model_id,
            "suite":suite.name,"suite_version":suite_version,"attack_template":"AgentDojo DirectAttack",
            "api_parameters":api_parameters,"created_utc":datetime.now(timezone.utc).isoformat(),
            "payload_sha256":hashlib.sha256(payload.encode()).hexdigest(),
            "checker":CHECKER,"user_utility":utility,"attack_success":security,
            "outcome":"scored"}

def append_trial(path,record):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if json.loads(line)["trial_id"]==record["trial_id"]:
                return False
    with target.open("a",encoding="utf-8") as fh:
        fh.write(json.dumps(record,ensure_ascii=False,sort_keys=True)+"\n")
        fh.flush()
    return True
