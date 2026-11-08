"""Regression checks for the no-network registration onboarding example."""
import importlib.util
from pathlib import Path

def test_registration_check():
    path = Path(__file__).resolve().parents[1] / "examples" / "registration_check.py"
    spec = importlib.util.spec_from_file_location("registration_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run_demo()
    assert result == {
        "registered": ["read_document", "send_email"],
        "denied_email_effects": 0,
        "read_effects": 1,
    }

def test_no_side_effect_on_denied_tool():
    from agentshield_guard import AgentShield, ToolPolicy, DeniedToolCall
    import pytest
    called = []
    def handler(**kwargs):
        called.append(kwargs)
    registry = AgentShield(ToolPolicy()).wrap_registry({"unknown": handler})
    with pytest.raises(DeniedToolCall, match="tool_not_allowlisted"):
        registry["unknown"](x="fixture")
    assert called == []
