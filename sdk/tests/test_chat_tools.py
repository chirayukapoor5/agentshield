"""Provider-format tool-call integration tests; no LLM or network required."""
import json

import pytest

from agentshield_guard import AgentShield, ToolPolicy
from agentshield_guard.chat_tools import MalformedToolCalls, dispatch_chat_tool_calls


def call(identifier="call_1", name="lookup", args='{"topic":"security"}'):
    return {"id": identifier, "type": "function",
            "function": {"name": name, "arguments": args}}


def test_real_handler_executed_through_guard():
    seen = []
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    result = dispatch_chat_tool_calls(
        shield, {"lookup": lambda topic: seen.append(topic) or {"topic": topic}},
        [call()])
    assert seen == ["security"]
    assert result[0]["role"] == "tool"
    assert result[0]["tool_call_id"] == "call_1"
    assert json.loads(result[0]["content"]) == {
        "ok": True, "result": {"topic": "security"}}


def test_unapproved_email_cannot_execute():
    seen = []
    shield = AgentShield(ToolPolicy(approval_tools={"send_email"}))
    result = dispatch_chat_tool_calls(
        shield, {"send_email": lambda to: seen.append(to)},
        [call(name="send_email", args='{"to":"outside@example.org"}')])
    assert seen == []
    assert json.loads(result[0]["content"])["error"] == "policy_denied"


def test_unknown_tool_never_executes():
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    result = dispatch_chat_tool_calls(shield, {"lookup": lambda: 1},
                                      [call(name="delete_file", args="{}")])
    assert json.loads(result[0]["content"])["error"] == "tool_not_registered"


def test_registered_but_unlisted_tool_denied():
    seen = []
    shield = AgentShield(ToolPolicy())
    result = dispatch_chat_tool_calls(
        shield, {"lookup": lambda topic: seen.append(topic)}, [call()])
    assert seen == []
    assert json.loads(result[0]["content"])["error"] == "policy_denied"


@pytest.mark.parametrize("bad", [
    [call(args='{"topic":"a","topic":"b"}')],
    [call(args='{"topic":NaN}')],
    [call(args='["not", "an", "object"]')],
    [call(args='{"topic":')], [call(args="null")],
    [call(identifier="")], [call(), call()],
    [dict(call(), type="custom")],
])
def test_invalid_batch_fails_closed_before_execution(bad):
    seen = []
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    with pytest.raises(MalformedToolCalls):
        dispatch_chat_tool_calls(shield,
            {"lookup": lambda topic: seen.append(topic)}, [call("ok"), *bad])
    assert seen == []


def test_oversized_arguments_fail_before_side_effects():
    seen = []
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    with pytest.raises(MalformedToolCalls):
        dispatch_chat_tool_calls(shield,
            {"lookup": lambda topic: seen.append(topic)},
            [call(args=json.dumps({"topic": "x" * 100}))],
            max_argument_bytes=40)
    assert seen == []


def test_batch_count_cap():
    with pytest.raises(MalformedToolCalls):
        dispatch_chat_tool_calls(AgentShield(ToolPolicy()), {},
                                  [call("1"), call("2")], max_calls=1)


def test_audit_failure_stops_execution():
    executed = []
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}),
                        audit=lambda _: (_ for _ in ()).throw(OSError()))
    messages = dispatch_chat_tool_calls(
        shield, {"lookup": lambda topic: executed.append(topic)}, [call()])
    assert executed == []
    assert json.loads(messages[0]["content"])["error"] == "policy_denied"


def test_approved_effectful_tool_executes_only_with_exact_true():
    seen = []
    shield = AgentShield(ToolPolicy(approval_tools={"send_email"}),
                        approve=lambda name, args: name == "send_email"
                        and args.get("to") == "approved@example.org")
    messages = dispatch_chat_tool_calls(shield,
        {"send_email": lambda to: seen.append(to) or "sent"},
        [call("a", "send_email", '{"to":"approved@example.org"}'),
         call("b", "send_email", '{"to":"other@example.org"}')])
    assert seen == ["approved@example.org"]
    assert [json.loads(x["content"])["ok"] for x in messages] == [True, False]


def test_handler_exception_has_no_exception_detail():
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    def broken(topic):
        raise RuntimeError("secret configuration details")
    message = dispatch_chat_tool_calls(shield, {"lookup": broken},
                                        [call()])[0]
    assert "secret configuration details" not in message["content"]
    assert json.loads(message["content"])["error"] == "tool_execution_failed"



@pytest.mark.parametrize("raw", [
    '{"text":"\ud800"}',
    '{"text":"\\ud800"}',
    '{"te\\udfffxt":"data"}',
    '{"nested":[{"text":"\\ud800"}]}',
])
def test_unpaired_unicode_surrogates_fail_closed_before_batch_side_effects(raw):
    executions = []
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    with pytest.raises(MalformedToolCalls):
        dispatch_chat_tool_calls(
            shield, {"lookup": lambda text: executions.append(text)},
            [call(identifier="first", name="lookup", args='{"topic":"safe"}'),
             call(identifier="bad", name="lookup", args=raw)],
        )
    assert executions == []


@pytest.mark.parametrize("bad_id,bad_name", [
    ("\ud800", "lookup"),
    ("normal", "lookup\udfff"),
])
def test_invalid_unicode_in_tool_metadata_rejects_batch(bad_id, bad_name):
    seen = []
    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    with pytest.raises(MalformedToolCalls):
        dispatch_chat_tool_calls(
            shield, {"lookup": lambda topic: seen.append(topic)},
            [call(identifier="first", args='{"topic":"ok"}'),
             call(identifier=bad_id, name=bad_name, args='{"topic":"bad"}')],
        )
    assert not seen
