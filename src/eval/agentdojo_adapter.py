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

def load_workspace(benchmark_version="v1.2.2"):
    """Load the pinned built-in workspace suite; do not generate synthetic tasks."""
    require_agentdojo()
    from agentdojo.task_suite.load_suites import get_suite
    return get_suite(benchmark_version, "workspace")


def evaluate_official(*, pipeline, user_task_id, injection_task_id, injection_slot,
                      injection_text, suite=None, benchmark_version="v1.2.2"):
    """Return (official_user_utility, official_attack_success).

    The caller must construct a real AgentDojo BasePipelineElement with an LLM
    adapter and selected defense; do not pass a mock pipeline for research metrics.
    """
    require_agentdojo()
    suite = load_workspace(benchmark_version) if suite is None else suite
    user_task = suite.get_user_task_by_id(user_task_id)
    injection_task = suite.get_injection_task_by_id(injection_task_id)
    valid_slots = suite.get_injection_vector_defaults()
    if injection_slot not in valid_slots:
        raise ValueError("unknown AgentDojo injection slot")
    utility, security = suite.run_task_with_pipeline(
        agent_pipeline=pipeline,
        user_task=user_task,
        injection_task=injection_task,
        injections={injection_slot: injection_text},
        verbose=False,
    )
    if type(utility) is not bool or type(security) is not bool:
        raise AgentDojoUnavailable("official checkers did not return booleans")
    return {"user_utility": utility, "attack_success": security,
            "checker": "agentdojo.TaskSuite.run_task_with_pipeline",
            "benchmark_version": benchmark_version}
