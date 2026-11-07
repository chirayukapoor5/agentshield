"""A real LangGraph ToolNode call guarded by AgentShield.

Installation (repository root):
    python -m pip install './sdk[langgraph]'
    python sdk/examples/langgraph_toolnode.py

No API key, LLM, network requests, real email or device file operation.
The only tool side effect is appending a fictional email to an in-memory list.
"""
from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import START, END, MessagesState, StateGraph

from agentshield_guard import AgentShield, ToolPolicy, wrap_langchain_tools


def demo() -> dict:
    fake_outbox: list[str] = []
    approved_recipients: set[str] = set()

    @tool
    def read_document(document_id: str) -> str:
        """Read a synthetic project document by identifier."""
        return f"Synthetic document {document_id}: tool results are untrusted data."

    @tool
    def send_email(to: str, body: str) -> str:
        """Store a fictional email in this example's memory-only outbox."""
        fake_outbox.append(f"{to}:{body}")
        return "Fictional outbox entry saved, no email delivered."

    def human_approval(tool_name: str, args: dict) -> bool:
        # Stand-in for a real reviewer. Do not allow an LLM to add entries here.
        if tool_name != "send_email":
            return False
        recipient = args.get("to")
        if recipient in approved_recipients:
            approved_recipients.remove(recipient)
            return True
        return False

    shield = AgentShield(
        ToolPolicy(
            read_only_tools={"read_document"},
            approval_tools={"send_email"},
        ),
        approve=human_approval,
    )
    # SECURITY: feed *only these* wrapped tool definitions to both the
    # model's bind_tools and ToolNode. The raw tools remain unprotected.
    secured = wrap_langchain_tools(shield, [read_document, send_email])
    builder = StateGraph(MessagesState)
    builder.add_node("tools", ToolNode(secured))
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    graph = builder.compile()

    def tool_call(name: str, args: dict, identifier: str) -> str:
        message = AIMessage(content="", tool_calls=[{
            "name": name, "args": args, "id": identifier, "type": "tool_call"
        }])
        outcome = graph.invoke({"messages": [message]})
        return str(outcome["messages"][-1].content)

    read = tool_call("read_document", {"document_id": "sample-1"}, "call_read")
    denied = tool_call("send_email", {
        "to": "demo@example.org", "body": "Synthetic only"
    }, "call_denied")
    approved_recipients.add("demo@example.org")  # Human approval, not LLM input
    approved = tool_call("send_email", {
        "to": "demo@example.org", "body": "Synthetic only"
    }, "call_approved")
    denied_again = tool_call("send_email", {
        "to": "demo@example.org", "body": "Synthetic only"
    }, "call_denied_again")
    return {
        "read": read,
        "denied": json.loads(denied),
        "approved": approved,
        "denied_again": json.loads(denied_again),
        "fictional_outbox_count": len(fake_outbox),
        "real_email_delivered": False,
        "model_invocations": 0,
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, sort_keys=True))
