"""AgentShield authorization boundary for all MCP tool handlers."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from agentshield_guard.guard import AgentShield, Decision, ToolPolicy

TOOL_NAMES = frozenset({"list_ci_runs", "get_ci_run", "get_test_summary", "list_failed_tests"})


def default_policy() -> ToolPolicy:
    return ToolPolicy(read_only_tools=TOOL_NAMES)


def guarded_registry(handlers: Mapping[str, Callable[..., Any]], *, policy: ToolPolicy | None = None,
                     audit: Callable[[Decision], None] | None = None) -> dict[str, Callable[..., Any]]:
    shield = AgentShield(default_policy() if policy is None else policy, audit=audit)
    return shield.wrap_registry(handlers)
