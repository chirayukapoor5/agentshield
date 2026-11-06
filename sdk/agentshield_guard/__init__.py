"""AgentShield: explicit, local tool-call authorization for Python agents.

No LLM classifier or remote telemetry is used. This is *not* a complete
prompt-injection defense and cannot secure calls that bypass its wrapper.
"""
from .guard import AgentShield, Decision, DeniedToolCall, ToolPolicy
from .chat_tools import MalformedToolCalls, dispatch_chat_tool_calls
from .agent_loop import AgentRun, ModelProtocolError, run_tool_agent
from .groq_transport import GroqChatTransport, GroqTransportError

__all__ = ["AgentShield", "Decision", "DeniedToolCall", "ToolPolicy", "MalformedToolCalls", "dispatch_chat_tool_calls", "AgentRun", "ModelProtocolError", "run_tool_agent",
           "GroqChatTransport", "GroqTransportError"]
__version__ = "0.1.0"
