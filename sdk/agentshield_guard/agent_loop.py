"""Bounded OpenAI-compatible local tool-use loop for AgentShield.

The transport is injectable for fully offline tests. A model's requested
functions are NEVER executed directly; execution flows through AgentShield.
This is a controlled research/SDK adapter, not a sandbox or network firewall.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .chat_tools import MalformedToolCalls, dispatch_chat_tool_calls
from .guard import AgentShield


class ModelProtocolError(RuntimeError):
    """The model response does not match the supported chat-completions format."""


@dataclass(frozen=True)
class AgentRun:
    """Result and redacted execution metadata; no prompts or tool arguments."""

    final_text: str | None
    finished: bool
    model_calls: int
    requested_tool_calls: int
    tool_outcomes: tuple[dict[str, str], ...]
    stop_reason: str


def run_tool_agent(
    *,
    shield: AgentShield,
    handlers: Mapping[str, Callable[..., Any]],
    tools: Sequence[Mapping[str, Any]],
    messages: Sequence[Mapping[str, Any]],
    transport: Callable[[dict[str, Any]], Mapping[str, Any]],
    model: str,
    max_model_calls: int = 3,
    max_tool_calls: int = 8,
    max_result_chars: int = 16_384,
) -> AgentRun:
    """Run a bounded local-function chat loop and return a redacted trace.

    `transport` receives a JSON-compatible OpenAI chat-completion payload and
    returns the JSON response. No provider credentials are needed for offline
    tests. Invalid model output raises before its tool batch is executed.

    Model/API calls can fail independently; callers must report those failures,
    not silently count them as safe refusals. Authorize every handler via
    ToolPolicy; the dispatcher will enforce the policy on every invocation.
    """
    if not isinstance(shield, AgentShield) or not callable(transport):
        raise TypeError("shield and transport are required")
    if (not isinstance(model, str) or not model
            or type(max_model_calls) is not int or not 1 <= max_model_calls <= 20
            or type(max_tool_calls) is not int or not 1 <= max_tool_calls <= 64
            or type(max_result_chars) is not int or not 128 <= max_result_chars <= 100_000):
        raise ValueError("invalid bounded run configuration")
    if not isinstance(handlers, Mapping) or not isinstance(tools, (tuple, list)):
        raise TypeError("handlers must be a mapping and tools a sequence")
    # Refuse built-in/remote provider-side tools that bypass this local guard.
    advertised: set[str] = set()
    for entry in tools:
        if not isinstance(entry, Mapping) or entry.get("type") != "function":
            raise ValueError("only local function tool definitions are supported")
        fn = entry.get("function")
        name = fn.get("name") if isinstance(fn, Mapping) else None
        if not isinstance(name, str) or not name or name in advertised or name not in handlers:
            raise ValueError("tools must name distinct registered handlers")
        advertised.add(name)
    if not advertised:
        raise ValueError("at least one local function tool must be advertised")
    if not isinstance(messages, (list, tuple)) or not messages:
        raise ValueError("nonempty messages required")
    try:
        conversation = json.loads(json.dumps(list(messages), allow_nan=False))
        definitions = json.loads(json.dumps(list(tools), allow_nan=False))
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("messages and tools must be JSON-compatible") from exc
    if not all(isinstance(msg, dict) and msg.get("role") in
               {"system", "developer", "user", "assistant", "tool"}
               for msg in conversation):
        raise ValueError("unsupported message role")
    events: list[dict[str, str]] = []
    total_calls = 0
    for step in range(max_model_calls):
        request = {"model": model, "messages": conversation, "tools": definitions,
                   "tool_choice": "auto", "parallel_tool_calls": False,
                   "temperature": 0, "max_completion_tokens": 512}
        response = transport(request)
        if not isinstance(response, Mapping):
            raise ModelProtocolError("provider response must be an object")
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ModelProtocolError("expected exactly one completion choice")
        choice = choices[0]
        if not isinstance(choice, Mapping) or not isinstance(choice.get("message"), Mapping):
            raise ModelProtocolError("missing assistant message")
        assistant = choice["message"]
        if assistant.get("role") != "assistant":
            raise ModelProtocolError("unexpected completion role")
        calls = assistant.get("tool_calls") or []
        if calls and not isinstance(calls, list):
            raise ModelProtocolError("tool_calls must be a list")
        if calls:
            if total_calls + len(calls) > max_tool_calls:
                return AgentRun(None, False, step + 1, total_calls,
                                tuple(events), "tool_call_budget_exhausted")
            # Refuse unknown advertised tool IDs. In particular, do not trust
            # provider-side built-ins or made-up tools as locally executable.
            for call in calls:
                fn = call.get("function") if isinstance(call, Mapping) else None
                if not isinstance(fn, Mapping) or fn.get("name") not in advertised:
                    raise ModelProtocolError("model requested an unadvertised tool")
            # Dispatcher validates the entire batch before the first side effect.
            try:
                tool_messages = dispatch_chat_tool_calls(
                    shield, handlers, calls, max_calls=max_tool_calls)
            except MalformedToolCalls as exc:
                raise ModelProtocolError("invalid tool-call batch") from exc
            total_calls += len(calls)
            safe_calls = json.loads(json.dumps(calls, allow_nan=False))
            conversation.append({"role": "assistant", "content": assistant.get("content"),
                                 "tool_calls": safe_calls})
            for call, result in zip(calls, tool_messages):
                body = result["content"]
                if len(body) > max_result_chars:
                    body = json.dumps({"ok": False, "error": "tool_output_limit"})
                parsed = json.loads(body)
                events.append({"tool": call["function"]["name"],
                               "status": "allowed" if parsed.get("ok") else
                                         str(parsed.get("error", "unknown"))})
                conversation.append({"role": "tool",
                                     "tool_call_id": result["tool_call_id"],
                                     "content": body})
            continue
        finish = choice.get("finish_reason")
        if finish != "stop":
            raise ModelProtocolError("incomplete assistant response")
        content = assistant.get("content")
        if not isinstance(content, str):
            raise ModelProtocolError("final response must be text")
        return AgentRun(content, True, step + 1, total_calls,
                        tuple(events), "completed")
    return AgentRun(None, False, max_model_calls, total_calls,
                    tuple(events), "model_call_budget_exhausted")
