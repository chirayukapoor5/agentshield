from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
sys.path.insert(0, str(EXAMPLES))

import ci_triage_demo as demo


@pytest.mark.asyncio
async def test_offline_demo_uses_mcp_protocol_and_marks_fixtures():
    result = await demo.run_demo()
    assert result["mode"] == "offline"
    assert result["runs"]["status"] == "ok"
    assert result["runs"]["is_fixture"] is True
    assert [row["workflow"] for row in result["runs"]["runs"]] == ["research", "sdk"]
    assert result["run_detail"]["is_fixture"] is True
    assert result["run_detail"]["run"]["id"] == 9002
    assert result["test_summary"]["status"] == "ok"
    assert result["test_summary"]["is_fixture"] is True
    assert result["test_summary"]["report"]["failed"] == 1
    assert result["failed_tests"]["status"] == "ok"
    assert result["failed_tests"]["failed_tests"] == ["a" * 64]


@pytest.mark.asyncio
async def test_model_requires_both_explicit_opt_in_flags():
    with pytest.raises(ValueError):
        await demo.run_demo(model="fixture-model")
    with pytest.raises(ValueError):
        await demo.run_demo(allow_model_call=True)
    with pytest.raises(ValueError):
        await demo.run_demo(live=True, model="fixture-model", allow_model_call=True)


def _tool_call(name: str, arguments: str = '{"workflow":"research","limit":2}') -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call-1", "type": "function", "function": {"name": name, "arguments": arguments}}
    ]}, "finish_reason": "tool_calls"}]}


def _final(content: str = "fixture output includes private-test-string") -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


def _failed_tests_call() -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call-2", "type": "function", "function": {"name": "list_failed_tests", "arguments": '{"run_id":9002,"limit":10}'}}
    ]}, "finish_reason": "tool_calls"}]}


@pytest.mark.asyncio
async def test_fake_model_tool_request_flows_through_mcp_and_only_trace_is_returned():
    calls = []

    def transport(request):
        calls.append(request)
        return _tool_call("list_ci_runs") if len(calls) == 1 else _failed_tests_call() if len(calls) == 2 else _final()

    result = await demo.run_demo(model="offline-test-model", allow_model_call=True, model_transport=transport)
    assert len(calls) == 3
    assert result["runs"]["is_fixture"] is True
    trace = result["model_trace"]
    assert trace["requested_tool_calls"] == 2
    assert trace["tool_outcomes"] == [{"tool": "list_ci_runs", "status": "allowed"},
                                       {"tool": "list_failed_tests", "status": "allowed"}]
    assert "final_text" not in trace
    assert "private-test-string" not in str(result)


def test_unknown_tool_and_exhausted_budget_have_no_handler_side_effects():
    from agentshield_guard import AgentShield, ModelProtocolError, ToolPolicy, run_tool_agent

    calls = []
    def handler(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    definition = [{"type": "function", "function": {"name": "safe_tool", "parameters": {"type": "object", "properties": {}}}}]
    shield = AgentShield(ToolPolicy(read_only_tools=frozenset({"safe_tool"})))
    messages = [{"role": "user", "content": "read"}]
    with pytest.raises(ModelProtocolError):
        run_tool_agent(shield=shield, handlers={"safe_tool": handler}, tools=definition,
                       messages=messages, transport=lambda _: _tool_call("unknown_tool"), model="fake",
                       max_model_calls=3, max_tool_calls=4)
    assert calls == []

    def over_budget(_request):
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"call-{i}", "type": "function", "function": {"name": "safe_tool", "arguments": "{}"}}
            for i in range(5)
        ]}, "finish_reason": "tool_calls"}]}

    exhausted = run_tool_agent(shield=shield, handlers={"safe_tool": handler}, tools=definition,
                               messages=messages, transport=over_budget, model="fake",
                               max_model_calls=3, max_tool_calls=4)
    assert exhausted.stop_reason == "tool_call_budget_exhausted"
    assert calls == []
