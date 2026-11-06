"""Minimal bounded Groq chat-completions transport, no third-party dependencies.

Only calls the fixed Groq API origin. Provider errors are redacted: do not log
response bodies, headers, secrets, prompt text, or tool arguments.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping

GROQ_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqTransportError(RuntimeError):
    """Redacted provider failure; never includes credentials or raw content."""


class GroqChatTransport:
    def __init__(self, api_key: str, *, timeout: float = 30.0,
                 max_response_bytes: int = 2_000_000):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("GROQ_API_KEY is required")
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
            raise ValueError("timeout must be between 1 and 120 seconds")
        if type(max_response_bytes) is not int or not 1024 <= max_response_bytes <= 8_000_000:
            raise ValueError("invalid provider response limit")
        self._key = api_key
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes

    def __call__(self, request_payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request_payload, Mapping):
            raise TypeError("request payload must be a mapping")
        # No logs containing request bodies. The provider necessarily receives
        # the current conversation; use only synthetic data in research runs.
        try:
            payload = json.dumps(dict(request_payload), allow_nan=False).encode("utf-8")
            request = urllib.request.Request(
                GROQ_COMPLETIONS_URL, data=payload, method="POST",
                headers={"Authorization": "Bearer " + self._key,
                         "Content-Type": "application/json",
                         "User-Agent": "AgentShield-ToolResearch/0.1"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise GroqTransportError("provider_response_oversized")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise GroqTransportError("invalid_provider_json")
            return result
        except urllib.error.HTTPError as exc:
            # Never expose provider response bodies or request payloads.
            raise GroqTransportError("provider_http_" + str(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GroqTransportError("provider_connection_error") from None
        except (ValueError, UnicodeError):
            raise GroqTransportError("invalid_provider_json") from None
