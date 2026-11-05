"""Deterministic candidate selection on the actual AgentDojo workspace suite."""
from __future__ import annotations
import hashlib
import json
import random
from pathlib import Path

from src.eval.agentdojo_adapter import load_workspace

def sample_pairs(suite=None, count=30, seed=20261105):
    if suite is None:
        suite=load_workspace()
    from agentdojo.attacks.baseline_attacks import DirectAttack
    attack=DirectAttack(suite, target_pipeline=None)
    candidates=[]
    exclusions=[]
    for uid in sorted(suite.user_tasks):
        user_task=suite.user_tasks[uid]
        try:
            slots=sorted(attack.get_injection_candidates(user_task))
        except ValueError as exc:
            exclusions.append({"user_task_id":uid,"reason":str(exc)})
            continue
        for iid in sorted(suite.injection_tasks):
            for slot in slots:
                candidates.append({"user_task_id":uid,"injection_task_id":iid,"injection_slot":slot})
    rng=random.Random(seed)
    rng.shuffle(candidates)
    # Group by original user task to prevent task leakage between splits.
    selected=candidates[:count]
    if len(selected)<count:
        raise ValueError(f"requested {count} pairs but only {len(selected)} are available")
    return {"suite":suite.name,"seed":seed,"count":len(selected),"pairs":selected,
            "excluded_noninjectable_user_tasks":exclusions,
            "warning":"Selection is a seeded subset, not a random split across independent scenario families."}

def write_manifest(path,manifest):
    output=Path(path)
    output.parent.mkdir(parents=True,exist_ok=True)
    blob=json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)
    output.write_text(blob+"\n",encoding="utf-8")
    return hashlib.sha256(blob.encode()).hexdigest()
