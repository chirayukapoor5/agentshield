"""OpenAI-compatible chat-completion tool-call dispatcher.

Accepts the `tool_calls` array from an assistant chat completion. The
caller supplies *raw* local handlers; this dispatcher wraps them using
AgentShield before any execution. It makes no HTTP requests and does not
trust a model's tool choice or JSON arguments.
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, Mapping, Sequence

from .guard import AgentShield, DeniedToolCall, _has_invalid_unicode


class MalformedToolCalls(ValueError):
    """Reject an entire malformed tool-call batch before side effects."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _parse_calls(
    calls: Sequence[Mapping[str, Any]], *, max_calls: int, max_argument_bytes: int
) -> list[tuple[str, str, dict[str, Any]]]:
    if (not isinstance(calls, (list, tuple)) or isinstance(max_calls, bool)
            or not isinstance(max_calls, int) or max_calls < 1
            or isinstance(max_argument_bytes, bool)
            or not isinstance(max_argument_bytes, int) or max_argument_bytes < 1):
        raise MalformedToolCalls("invalid tool-call limits or collection")
    if len(calls) > max_calls:
        raise MalformedToolCalls("tool-call batch limit exceeded")
    verified: list[tuple[str, str, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for call in calls:
        if not isinstance(call, Mapping) or call.get("type") != "function":
            raise MalformedToolCalls("unsupported tool-call envelope")
        identifier = call.get("id")
        function = call.get("function")
        if (not isinstance(identifier, str) or not identifier or identifier in seen_ids
                or len(identifier) > 256 or not isinstance(function, Mapping)):
            raise MalformedToolCalls("missing or duplicate tool-call ID")
        seen_ids.add(identifier)
        name = function.get("name")
        raw = function.get("arguments")
        if not isinstance(name, str) or not name or len(name) > 256:
            raise MalformedToolCalls("invalid tool name")
        if not isinstance(raw, str):
            raise MalformedToolCalls("invalid or oversized tool arguments")
        if len(raw) > max_argument_bytes:
            # Avoid allocating encoded multi-byte copies of enormous input.
            raise MalformedToolCalls("invalid or oversized tool arguments")
        try:
            byte_count = len(raw.encode("utf-8"))
        except UnicodeError as exc:
            raise MalformedToolCalls("invalid UTF-8 tool arguments") from exc
        if byte_count > max_argument_bytes:
            raise MalformedToolCalls("invalid or oversized tool arguments")
        try:
            args = json.loads(raw, object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise MalformedToolCalls("invalid tool arguments JSON") from exc
        if not isinstance(args, dict):
            raise MalformedToolCalls("tool arguments must be a JSON object")
        if (_has_invalid_unicode(identifier) or _has_invalid_unicode(name)
                or _has_invalid_unicode(args)):
            raise MalformedToolCalls("invalid Unicode in tool-call data")
        verified.append((identifier, name, args))
    return verified


def dispatch_chat_tool_calls(
    shield: AgentShield,
    handlers: Mapping[str, Callable[..., Any]],
    tool_calls: Sequence[Mapping[str, Any]],
    *,
    max_calls: int = 8,
    max_argument_bytes: int = 16_384,
) -> list[dict[str, str]]:
    """Validate then execute a chat-completion tool-call batch.

    Pass the returned messages back to the model as role='tool' messages.
    Invalid batches raise MalformedToolCalls *before* executing any handler.
    Unknown and denied tools produce structured denied responses. The output
    contains handler data, so treat it as untrusted model-facing content.
    This does not sandbox handlers or validate their claimed read-only status.
    """
    if not isinstance(shield, AgentShield):
        raise TypeError("shield must be an AgentShield instance")
    verified = _parse_calls(tool_calls, max_calls=max_calls,
                            max_argument_bytes=max_argument_bytes)
    secured = shield.wrap_registry(handlers)
    messages: list[dict[str, str]] = []
    for identifier, name, args in verified:
        if name not in secured:
            payload: dict[str, Any] = {"ok": False, "error": "tool_not_registered"}
        else:
            try:
                value = secured[name](**args)
                # Avoid leaking handler internals if the return is not JSON safe.
                serialized = json.dumps(value, allow_nan=False)
                payload = {"ok": True, "result": json.loads(serialized)}
            except DeniedToolCall:
                payload = {"ok": False, "error": "policy_denied"}
            except Exception:
                payload = {"ok": False, "error": "tool_execution_failed"}
        messages.append({"role": "tool", "tool_call_id": identifier,
                         "content": json.dumps(payload, allow_nan=False,
                                               sort_keys=True)})
    return messages
