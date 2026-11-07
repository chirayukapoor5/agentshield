"""Run: PYTHONPATH=sdk python sdk/examples/quickstart.py (from repository root)."""
from agentshield_guard import AgentShield, ToolPolicy, DeniedToolCall

activity = []
shield = AgentShield(
    ToolPolicy(read_only_tools=frozenset({"lookup"}),
               approval_tools=frozenset({"send_message"})),
    audit=lambda event: activity.append({"tool": event.tool, "allowed": event.allowed, "reason": event.reason}),
)

def lookup(topic: str) -> str:
    return f"Synthetic fact about {topic}"

def send_message(recipient: str, text: str) -> str:
    return "Synthetic message was sent"

safe_lookup = shield.guard("lookup", lookup)
safe_send = shield.guard("send_message", send_message)
print(safe_lookup(topic="security"))
try:
    print(safe_send(recipient="example", text="hello"))
except DeniedToolCall as exc:
    print("Blocked:", exc)
print("Audit:", activity)
