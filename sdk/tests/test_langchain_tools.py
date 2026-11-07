"""Real LangChain / LangGraph integration tests, completely offline.

These run with the actual optional libraries in CI. A model cannot make any
network or real tool calls here; all handlers mutate local test arrays only.
"""
from __future__ import annotations

import json

import pytest

langchain_tools = pytest.importorskip("langchain_core.tools")
from agentshield_guard import AgentShield, ToolPolicy, wrap_langchain_tools

tool = langchain_tools.tool


def test_read_only_tool_invoked_through_policy_and_schema_preserved():
    seen = []

    @tool
    def lookup(document_id: str) -> str:
        """Read a synthetic document by ID."""
        seen.append(document_id)
        return "synthetic:" + document_id

    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    guarded = wrap_langchain_tools(shield, [lookup])
    assert len(guarded) == 1
    assert guarded[0].name == "lookup"
    assert guarded[0].args_schema == lookup.args_schema
    assert guarded[0].invoke({"document_id": "demo-1"}) == "synthetic:demo-1"
    assert seen == ["demo-1"]


def test_unapproved_email_is_blocked_before_original_handler():
    sent = []

    @tool
    def send_email(to: str, body: str) -> str:
        """Send a fictional email."""
        sent.append((to, body))
        return "saved to sandbox"

    shield = AgentShield(ToolPolicy(approval_tools={"send_email"}))
    guarded = wrap_langchain_tools(shield, [send_email])[0]
    value = guarded.invoke({"to": "demo@example.org", "body": "hello"})
    assert json.loads(value) == {"ok": False, "error": "policy_denied"}
    assert sent == []


def test_one_time_approval_cannot_authorize_second_tool_call():
    outbox = []
    remaining = [True]

    @tool
    def send_email(to: str) -> str:
        """Save a fictional message."""
        outbox.append(to)
        return "offline-only"

    def approve(name, args):
        if name == "send_email" and remaining[0] and args["to"] == "demo@example.org":
            remaining[0] = False
            return True
        return False

    guarded = wrap_langchain_tools(
        AgentShield(ToolPolicy(approval_tools={"send_email"}), approve=approve),
        [send_email])[0]
    assert guarded.invoke({"to": "demo@example.org"}) == "offline-only"
    assert json.loads(guarded.invoke({"to": "demo@example.org"}))["error"] == "policy_denied"
    assert outbox == ["demo@example.org"]


def test_destination_filter_stops_unlisted_hostname():
    accessed = []

    @tool
    def fetch_url(url: str) -> str:
        """Fetch a fictional offline resource."""
        accessed.append(url)
        return "offline page"

    shield = AgentShield(ToolPolicy(
        read_only_tools={"fetch_url"}, allowed_hosts={"docs.agentshield.test"},
        url_args={"fetch_url": ("url",)}))
    wrapped = wrap_langchain_tools(shield, [fetch_url])[0]
    assert json.loads(wrapped.invoke({"url": "https://other.test/"}))["error"] == "policy_denied"
    assert accessed == []
    assert wrapped.invoke({"url": "https://docs.agentshield.test/guide"}) == "offline page"
    assert accessed == ["https://docs.agentshield.test/guide"]


def test_unallowlisted_tool_is_denied_even_when_provided_to_adapter():
    calls = []

    @tool
    def delete_file(path: str) -> str:
        """Delete a fictional file."""
        calls.append(path)
        return "deleted"

    wrapped = wrap_langchain_tools(AgentShield(ToolPolicy()), [delete_file])[0]
    assert json.loads(wrapped.invoke({"path": "sample.txt"}))["error"] == "policy_denied"
    assert calls == []


def test_audit_failure_is_fail_closed():
    calls = []

    @tool
    def lookup(document_id: str) -> str:
        """Lookup a synthetic document."""
        calls.append(document_id)
        return "ok"

    def broken_audit(_):
        raise OSError("secret-audit-log-path")

    wrapped = wrap_langchain_tools(AgentShield(
        ToolPolicy(read_only_tools={"lookup"}), audit=broken_audit), [lookup])[0]
    value = wrapped.invoke({"document_id": "test"})
    assert json.loads(value)["error"] == "policy_denied"
    assert "secret-audit-log-path" not in value
    assert calls == []


def test_handler_errors_sanitized():
    @tool
    def lookup(document_id: str) -> str:
        """Read an offline document."""
        raise RuntimeError("VERY_SENSITIVE_HANDLER_EXCEPTION")

    wrapped = wrap_langchain_tools(AgentShield(
        ToolPolicy(read_only_tools={"lookup"})), [lookup])[0]
    value = wrapped.invoke({"document_id": "test"})
    assert json.loads(value) == {"ok": False, "error": "tool_execution_failed"}
    assert "VERY_SENSITIVE" not in value


def test_rejects_duplicate_names_and_non_structured_tool():
    @tool
    def lookup(document_id: str) -> str:
        """Lookup synthetic document."""
        return document_id

    shield = AgentShield(ToolPolicy(read_only_tools={"lookup"}))
    with pytest.raises(ValueError, match="distinct"):
        wrap_langchain_tools(shield, [lookup, lookup])
    with pytest.raises(TypeError, match="StructuredTool"):
        wrap_langchain_tools(shield, [object()])
    with pytest.raises(ValueError, match="nonempty"):
        wrap_langchain_tools(shield, [])


def test_real_langgraph_toolnode_uses_guarded_handler():
    pytest.importorskip("langgraph.prebuilt")
    from langchain_core.messages import AIMessage
    from langgraph.prebuilt import ToolNode
    from langgraph.graph import START, END, MessagesState, StateGraph

    sent = []

    @tool
    def send_email(to: str) -> str:
        """Send a synthetic, fictional message."""
        sent.append(to)
        return "saved"

    tools = wrap_langchain_tools(AgentShield(
        ToolPolicy(approval_tools={"send_email"})), [send_email])
    # Construct the exact model-generated tool-call message shape that
    # LangGraph ToolNode consumes. No live LLM is involved.
    call = AIMessage(content="", tool_calls=[{
        "name": "send_email",
        "args": {"to": "outside@example.org"},
        "id": "call_1",
        "type": "tool_call",
    }])
    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_edge(START, "tools")
    graph_builder.add_edge("tools", END)
    graph = graph_builder.compile()
    # Run inside a graph so LangGraph supplies its ToolRuntime/config, as
    # required by current releases of ToolNode.
    result = graph.invoke({"messages": [call]})
    assert len(result["messages"]) == 2
    response = result["messages"][-1]
    assert response.tool_call_id == "call_1"
    assert json.loads(response.content) == {"ok": False, "error": "policy_denied"}
    assert sent == []


def test_original_unwrapped_tool_remains_unprotected_by_design():
    seen = []

    @tool
    def read_document(document_id: str) -> str:
        """Read an offline synthetic item."""
        seen.append(document_id)
        return "fixture"

    wrap_langchain_tools(AgentShield(ToolPolicy()), [read_document])
    # This demonstrates the documented application responsibility: do not
    # pass original tools to ToolNode or model.bind_tools!
    assert read_document.invoke({"document_id": "original-call"}) == "fixture"
    assert seen == ["original-call"]



def test_runnable_langgraph_cookbook_completes_without_model():
    import runpy
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "examples" / "langgraph_toolnode.py"
    report = runpy.run_path(str(example))["demo"]()
    assert report["fictional_outbox_count"] == 1
    assert report["real_email_delivered"] is False
    assert report["model_invocations"] == 0
    assert "Synthetic document" in report["read"]
    assert report["denied"] == {"ok": False, "error": "policy_denied"}
    assert report["denied_again"] == {"ok": False, "error": "policy_denied"}
    assert "Fictional outbox entry saved" in report["approved"]



def test_async_only_structured_tool_refused_before_any_execution():
    called = []

    @tool
    async def async_lookup(document_id: str) -> str:
        """Read a fictional document with an async-only function."""
        called.append(document_id)
        return "fixture"

    with pytest.raises(ValueError, match="async-only"):
        wrap_langchain_tools(AgentShield(
            ToolPolicy(read_only_tools={"async_lookup"})), [async_lookup])
    assert called == []


def test_runtime_injected_arguments_refused_without_native_injection_support():
    # LangGraph injects ToolRuntime itself; the adapter must not strip
    # hidden state or silently invoke such a tool with model-supplied data.
    from langchain_core.tools import ToolRuntime

    @tool
    def inspect_runtime(document_id: str, runtime: ToolRuntime) -> str:
        """Inspect a synthetic document with graph run context."""
        return document_id

    with pytest.raises(ValueError, match="injected or hidden"):
        wrap_langchain_tools(AgentShield(ToolPolicy(
            read_only_tools={"inspect_runtime"})), [inspect_runtime])
