"""Offline onboarding check: register only guarded tool handlers.

Run: PYTHONPATH=sdk python sdk/examples/registration_check.py
No network, filesystem mutation, model calls or real messages.
"""
from agentshield_guard import AgentShield, DeniedToolCall, ToolPolicy


def run_demo():
    effects = []
    def read_document(document_id: str):
        effects.append(("read", document_id))
        return "fictional document"

    def send_email(recipient: str):
        effects.append(("email", recipient))
        return "fictional outbox entry"

    raw = {"read_document": read_document, "send_email": send_email}
    shield = AgentShield(ToolPolicy(
        read_only_tools={"read_document"},
        approval_tools={"send_email"},
    ))
    registered = shield.wrap_registry(raw)
    assert registered["read_document"] is not raw["read_document"], "Raw handler registered"
    assert registered["send_email"] is not raw["send_email"], "Raw handler registered"
    assert registered["read_document"](document_id="sample") == "fictional document"
    try:
        registered["send_email"](recipient="fictional@example.invalid")
    except DeniedToolCall:
        pass
    else:
        raise AssertionError("Email must be denied without explicit approval")
    assert effects == [("read", "sample")], "Denied tool executed a handler"
    return {"registered": sorted(registered), "denied_email_effects": 0, "read_effects": 1}


if __name__ == "__main__":
    print(run_demo())
