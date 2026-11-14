"""Deterministic toy examples. Not an AgentDojo benchmark or ASR measurement."""
import json
from agentshield_guard import AgentShield, ToolPolicy, DeniedToolCall

calls = []
shield = AgentShield(ToolPolicy(
    read_only_tools=frozenset({"read_document", "fetch_url"}),
    approval_tools=frozenset({"send_email", "delete_file"}),
    allowed_hosts=frozenset({"docs.example.org"}),
    url_args={"fetch_url": ("url",)},
), audit=lambda d: calls.append({"tool": d.tool, "allowed": d.allowed, "reason": d.reason}))

executed = []
def tool(**kwargs):
    executed.append(kwargs)
    return "ok"

cases = [
    ("read_document", {"id": "synthetic-1"}, True),
    ("send_email", {"to": "test@example.org"}, False),
    ("delete_file", {"path": "synthetic.txt"}, False),
    ("execute_shell", {"command": "echo demo"}, False),
    ("fetch_url", {"url": "https://docs.example.org/guide"}, True),
    ("fetch_url", {"url": "https://unlisted.example.org/guide"}, False),
    ("fetch_url", {"url": "http://docs.example.org/guide"}, False),
    ("fetch_url", {"url": "https://docs.example.org.evil.test"}, False),
]

correct = 0
for name, arguments, expected in cases:
    try:
        shield.guard(name, tool)(**arguments)
        allowed = True
    except DeniedToolCall:
        allowed = False
    correct += allowed == expected

print(json.dumps({
    "label": "DETERMINISTIC TOY POLICY DEMO — NOT REAL-WORLD DEFENSE ASR",
    "cases": len(cases), "expected_decisions_matched": correct,
    "allowed": sum(x["allowed"] for x in calls),
    "denied": sum(not x["allowed"] for x in calls),
    "real_llm_calls": 0,
    "agentdojo_trials": 0,
    "evidence": calls,
}, indent=2))
