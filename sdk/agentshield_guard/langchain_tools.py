"""Opt-in synchronous LangChain / LangGraph ToolNode integration.

Wrap pre-existing *synchronous StructuredTool* instances, keeping their
Pydantic argument schema while enforcing AgentShield before invoking any
original handler. Install with: pip install -e './sdk[langchain]'

Security scope:
- Pass ONLY the returned tools to the model and ToolNode. Calling original
  instances directly bypasses this wrapper.
- Injected run-time/state/store arguments and async-only tools are NOT
  supported: they are refused instead of silently dropping protected inputs.
- Policy denial is returned as a fixed structured string to let the model
  continue without executing a handler; no exception details are leaked.
- This is not handler isolation, network egress protection or prompt filtering.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .guard import AgentShield, DeniedToolCall


def _field_names(schema: Any) -> set[str]:
    """Recognize ordinary Pydantic model and JSON-schema field declarations."""
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("tool JSON schema must declare properties")
        return set(properties)
    fields = getattr(schema, "model_fields", None)
    if isinstance(fields, dict):
        return set(fields)
    fields = getattr(schema, "__fields__", None)
    if isinstance(fields, dict):
        return set(fields)
    raise ValueError("tool must have a Pydantic or JSON argument schema")


def wrap_langchain_tools(shield: AgentShield, tools: Sequence[Any]) -> list[Any]:
    """Convert synchronous LangChain StructuredTools into policy-gated tools.

    These can be passed directly to `langgraph.prebuilt.ToolNode`. Every
    invocation goes through `AgentShield.guard` before the original
    StructuredTool is called. Does not access or change global LangChain
    internals and does not require a model or API key.

    Argument validation performed by LangChain happens before this wrapper.
    Handler invocations, including when ToolNode executes tools concurrently,
    receive a JSON snapshot checked by AgentShield. Thread safety of approval
    callbacks and handlers remains the application's responsibility.
    """
    if not isinstance(shield, AgentShield):
        raise TypeError("shield must be an AgentShield instance")
    if not isinstance(tools, (tuple, list)) or not tools:
        raise ValueError("supply a nonempty list of LangChain tools")
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise ImportError("install the optional 'agentshield-guard[langchain]' extra") from exc

    seen: set[str] = set()
    result: list[Any] = []
    for original in tools:
        if not isinstance(original, StructuredTool):
            raise TypeError("only synchronous LangChain StructuredTool instances are supported")
        name = original.name
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("tool names must be nonempty and distinct")
        seen.add(name)
        if not callable(original.func):
            raise ValueError("async-only tools cannot be wrapped safely")
        if original.response_format != "content":
            raise ValueError("artifact-returning tools are not supported")
        source_schema = original.args_schema
        if source_schema is None:
            raise ValueError("explicit tool argument schema required")
        # A runtime/state-injected argument is absent from the model-visible
        # schema. Without native injection, a forwarded invocation would lose
        # it; reject instead of accidentally weakening the integration.
        if _field_names(source_schema) != _field_names(original.tool_call_schema):
            raise ValueError("injected or hidden tool arguments are not supported")
        secured = shield.guard(
            name, lambda _original=original, **kwargs: _original.invoke(kwargs)
        )

        def guarded_func(_secured=secured, **kwargs: Any) -> Any:
            try:
                return _secured(**kwargs)
            except DeniedToolCall:
                return json.dumps({"ok": False, "error": "policy_denied"}, sort_keys=True)
            except Exception:
                # Do not expose handler errors, file names or credentials to
                # the next LLM turn. Audit denial is already fail-closed.
                return json.dumps({"ok": False, "error": "tool_execution_failed"},
                                  sort_keys=True)

        adapted = StructuredTool.from_function(
            func=guarded_func,
            name=name,
            description=original.description,
            args_schema=source_schema,
            infer_schema=False,
            return_direct=original.return_direct,
            response_format="content",
        )
        result.append(adapted)
    return result
