"""Precisely name available baseline defenses; trained model not silently substituted."""
from src.eval.agentdojo_adapter import BUILTIN_DEFENSES_VERIFIED_IN_SOURCE

SELECTED = ("none", "tool_filter", "repeat_user_prompt", "learned_classifier")

def assert_ready(name, classifier_model=None, license_accepted=False):
    if name not in SELECTED:
        raise ValueError("defense is not preregistered")
    if name == "learned_classifier" and (not classifier_model or not license_accepted):
        raise RuntimeError("learned classifier requires an explicit model/revision and license/access review")
    if name != "none" and name != "learned_classifier" and name not in BUILTIN_DEFENSES_VERIFIED_IN_SOURCE:
        raise RuntimeError("AgentDojo defense name unknown")
    return name
