"""Deterministic allowlist / approval gate for executable agent tools.

Boundary: this wraps application-owned Python tool functions. It never claims
to alter the model's internal behavior or protect unwrapped call paths.
"""
from __future__ import annotations

import functools
import ipaddress
import json
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit


class DeniedToolCall(PermissionError):
    """Raised *before* tool execution when policy denies a call."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    tool: str
    requires_approval: bool = False


@dataclass(frozen=True)
class ToolPolicy:
    """Explicit tool authorization. All unlisted tools denied by default.

    read_only_tools / approval_tools are exact tool IDs, not patterns.
    allowed_hosts is an exact DNS hostname allowlist for URL-bearing calls.
    URL parameters must be declared with url_args for each tool to enforce
    outbound destination checks. IP-literal destinations are never permitted.
    """

    read_only_tools: frozenset[str] = field(default_factory=frozenset)
    approval_tools: frozenset[str] = field(default_factory=frozenset)
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    url_args: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Frozen dataclasses do not freeze the objects stored in their fields.
        # Take validated, immutable snapshots so callers cannot remove URL checks
        # after policy construction by mutating an input set or dictionary.
        for field_name in ("read_only_tools", "approval_tools", "allowed_hosts"):
            raw = getattr(self, field_name)
            if not isinstance(raw, (set, frozenset, tuple, list)):
                raise TypeError(f"{field_name} must be a collection of strings")
            if any(not isinstance(value, str) or not value for value in raw):
                raise ValueError(f"{field_name} must contain nonempty strings")
            object.__setattr__(self, field_name, frozenset(raw))

        if self.read_only_tools & self.approval_tools:
            raise ValueError("tools cannot be simultaneously read-only and approval-required")
        for host in self.allowed_hosts:
            if not _valid_dns_name(host):
                raise ValueError("allowed_hosts must be normalized DNS hostnames")

        if not isinstance(self.url_args, Mapping):
            raise TypeError("url_args must map tool names to URL argument names")
        checked_url_args: dict[str, tuple[str, ...]] = {}
        for tool, raw_names in self.url_args.items():
            if not isinstance(tool, str) or tool not in (self.read_only_tools | self.approval_tools):
                raise ValueError(f"URL-bearing tool {tool!r} must be explicitly authorized")
            if not isinstance(raw_names, (list, tuple)):
                raise ValueError("url_args values must be nonempty argument-name sequences")
            names = tuple(raw_names)
            if (not names or any(not isinstance(s, str) or not s.isidentifier() for s in names)
                    or len(names) != len(set(names))):
                raise ValueError("url_args values must be nonempty, unique argument names")
            checked_url_args[tool] = names
        object.__setattr__(self, "url_args", MappingProxyType(checked_url_args))


def _valid_dns_name(host: str) -> bool:
    if not isinstance(host, str) or host != host.lower() or len(host) > 253:
        return False
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
        return False
    if "." not in host or ".." in host:
        return False
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in host.split(".")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def _is_authorized_url(value: Any, hosts: frozenset[str]) -> bool:
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            return False
        if url.port not in (None, 443):
            return False
        hostname = url.hostname
        if not _valid_dns_name(hostname):
            return False
        return hostname in hosts
    except ValueError:
        return False


class AgentShield:
    """Wrap tool handlers; stop unauthorized calls before any side effect.

    approve receives (tool_name, plain-JSON-compatible arguments) and must
    explicitly return True. A raised error or any other value denies.
    """

    def __init__(self, policy: ToolPolicy, *, approve: Callable[[str, Mapping[str, Any]], bool] | None = None,
                 audit: Callable[[Decision], None] | None = None):
        self.policy = policy
        self.approve = approve
        self.audit = audit

    def decide(self, tool: str, arguments: Mapping[str, Any] | None = None) -> Decision:
        args = arguments or {}
        if not isinstance(tool, str) or not isinstance(args, Mapping):
            return Decision(False, "invalid_tool_request", str(tool))
        if tool in self.policy.read_only_tools:
            needs_approval = False
        elif tool in self.policy.approval_tools:
            needs_approval = True
        else:
            return Decision(False, "tool_not_allowlisted", tool)
        if tool in self.policy.url_args:
            for field_name in self.policy.url_args[tool]:
                if field_name not in args or not _is_authorized_url(args[field_name], self.policy.allowed_hosts):
                    return Decision(False, "destination_not_allowlisted", tool)
        if needs_approval:
            if self.approve is None:
                return Decision(False, "approval_not_configured", tool, True)
            try:
                checked = json.loads(json.dumps(dict(args), allow_nan=False))
                approved = self.approve(tool, checked) is True
            except Exception:
                approved = False
            if not approved:
                return Decision(False, "approval_denied", tool, True)
        return Decision(True, "allowlisted" if not needs_approval else "approved", tool, needs_approval)

    def guard(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Create an authorized wrapper. Register the wrapper as the agent tool."""
        @functools.wraps(fn)
        def wrapped(**arguments: Any) -> Any:
            # Execute precisely the JSON argument snapshot that was checked.
            # Without this boundary, an approval callback could mutate a
            # nested input object after approval but before handler execution.
            try:
                execution_args = json.loads(json.dumps(arguments, allow_nan=False))
            except (TypeError, ValueError, RecursionError) as exc:
                raise DeniedToolCall("invalid_tool_arguments") from exc
            decision = self.decide(name, execution_args)
            if self.audit is not None:
                try:
                    self.audit(decision)
                except Exception as exc:
                    raise DeniedToolCall("audit_failed") from exc
            if not decision.allowed:
                raise DeniedToolCall(f"{decision.tool}: {decision.reason}")
            return fn(**execution_args)
        return wrapped

    def wrap_registry(self, tools: Mapping[str, Callable[..., Any]]) -> dict[str, Callable[..., Any]]:
        """Return a new registry of guarded tools; the original is left untouched.

        Callers MUST register the returned registry, not the original one.
        Unknown tool names remain wrapped and fail closed at invocation.
        """
        if not isinstance(tools, Mapping) or any(
            not isinstance(name, str) or not callable(fn) for name, fn in tools.items()
        ):
            raise TypeError("tools must map tool names to callable handlers")
        return {name: self.guard(name, handler) for name, handler in tools.items()}
