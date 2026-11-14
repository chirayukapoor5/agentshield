"""Offline OpenAI-compatible tool-call demo; no API key required.

Run from repo root: PYTHONPATH=sdk python sdk/examples/chat_tool_calls.py
Real Groq/OpenAI-style chat completions can supply response.choices[0].message.tool_calls;
convert SDK objects with .model_dump() before dispatching.
"""
import json
from agentshield_guard import AgentShield, ToolPolicy, dispatch_chat_tool_calls

executed = []

def lookup(topic: str) -> dict:
    executed.append(("lookup", topic))
    return {"summary": "Synthetic security documentation", "topic": topic}

def send_email(to: str, body: str) -> str:
    executed.append(("send_email", to))
    return "synthetic send only"

shield = AgentShield(ToolPolicy(read_only_tools={"lookup"},
                               approval_tools={"send_email"}))
handlers = {"lookup": lookup, "send_email": send_email}
model_tool_calls = [
    {"id": "call_lookup", "type": "function",
     "function": {"name": "lookup", "arguments": '{"topic":"prompt injection"}'}},
    {"id": "call_mail", "type": "function",
     "function": {"name": "send_email",
                  "arguments": '{"to":"external@example.org","body":"sensitive"}'}},
]
messages = dispatch_chat_tool_calls(shield, handlers, model_tool_calls)
print(json.dumps({"tool_messages": messages, "handlers_executed": executed}, indent=2))
