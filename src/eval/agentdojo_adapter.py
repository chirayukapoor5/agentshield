"""Explicit AgentDojo integration guard.

The official AgentDojo benchmark runner/checkers are the ONLY scoring authority.
This module intentionally does not substitute fake evaluator results when unavailable.
"""
from importlib.metadata import PackageNotFoundError, version

PIN = "0.1.35"
BUILTIN_DEFENSES_VERIFIED_IN_SOURCE = (
    "tool_filter", "repeat_user_prompt", "spotlighting_with_delimiting",
    "transformers_pi_detector",
)

class AgentDojoUnavailable(RuntimeError):
    pass

def require_agentdojo():
    try:
        found = version("agentdojo")
    except PackageNotFoundError as exc:
        raise AgentDojoUnavailable("AgentDojo not installed; install research/requirements.txt") from exc
    if found != PIN:
        raise AgentDojoUnavailable(f"pinned AgentDojo {PIN} required; found {found}")
    import agentdojo
    return agentdojo

def verify_defenses():
    require_agentdojo()
    from agentdojo.agent_pipeline.agent_pipeline import DEFENSES
    absent = set(BUILTIN_DEFENSES_VERIFIED_IN_SOURCE) - set(DEFENSES)
    if absent:
        raise AgentDojoUnavailable(f"defense API drift: {sorted(absent)}")
    return list(DEFENSES)

def evaluate_official(*args, **kwargs):
    require_agentdojo()
    raise AgentDojoUnavailable(
        "Official AgentDojo pipeline/checker adapter not yet implemented. "
        "Do not report mock/local heuristics as AgentDojo ASR or utility."
    )
