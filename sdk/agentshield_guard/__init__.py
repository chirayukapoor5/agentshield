"""AgentShield: explicit, local tool-call authorization for Python agents.

No LLM classifier or remote telemetry is used. This is *not* a complete
prompt-injection defense and cannot secure calls that bypass its wrapper.
"""
from .guard import AgentShield, Decision, DeniedToolCall, ToolPolicy

__all__ = ["AgentShield", "Decision", "DeniedToolCall", "ToolPolicy"]
__version__ = "0.1.0"
