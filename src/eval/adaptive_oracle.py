"""Official training-oracle feedback for budget-matched adaptive searches.

Strictly forbids hidden held-out evaluations through this search path.
The official AgentDojo user-task and injection-task checkers alone determine
success; raw defender output is never returned to the attacker proposer.
"""
from __future__ import annotations

from collections.abc import Callable


def make_training_oracle(suite, pipeline, pair) -> Callable[[str], dict]:
    if not isinstance(pair, dict) or pair.get("split") not in {"dev", "tune"}:
        raise ValueError("adaptive feedback may use dev/tune scenarios only")
    from src.eval.agentdojo_adapter import require_agentdojo
    require_agentdojo()
    user = suite.get_user_task_by_id(pair["user_task_id"])
    attack = suite.get_injection_task_by_id(pair["injection_task_id"])
    slot = pair["injection_slot"]
    if not isinstance(slot, str) or not slot:
        raise ValueError("fixed injection slot required")

    def evaluate(candidate: str) -> dict:
        if not isinstance(candidate, str) or not candidate.strip() or len(candidate) > 10000:
            raise ValueError("invalid candidate injection")
        utility, success = suite.run_task_with_pipeline(
            agent_pipeline=pipeline, user_task=user, injection_task=attack,
            injections={slot: candidate}, verbose=False)
        if type(utility) is not bool or type(success) is not bool:
            raise ValueError("official AgentDojo checker must return two booleans")
        # Only the binary security checker outcome is visible to search.
        # Legitimate utility is NOT an attacker oracle feature.
        return {"success": success}

    return evaluate
