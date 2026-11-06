"""Transport, execution and smoke-demo tests: network disabled by monkeypatch."""
import io
import json
import urllib.error
from types import SimpleNamespace

import pytest

from agentshield_guard.groq_transport import (
    GROQ_COMPLETIONS_URL, GroqChatTransport, GroqTransportError, _NoRedirect,
)
from scripts.groq_tool_smoke import run


def fake_provider(monkeypatch, fn):
    monkeypatch.setattr("urllib.request.build_opener",
                        lambda *_: SimpleNamespace(open=fn))


def test_offline_scripted_injection_is_denied_without_email_execution():
    report = run("mock")
    assert report["run_type"] == "scripted_offline"
    assert report["finished"]
    assert report["synthetic_email_handler_executions"] == 0
    assert report["real_email_capability"] is False
    assert [x["status"] for x in report["tool_outcomes"]] == [
        "allowed", "policy_denied"]
    assert report["not_an_attack_success_rate"]


def test_groq_provider_uses_fixed_https_origin_and_passes_chat_payload(monkeypatch):
    captured = []
    class Reply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _):
            return b'{"choices":[{"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}'
    def fake_open(request, timeout):
        captured.append((request, timeout))
        return Reply()
    fake_provider(monkeypatch, fake_open)
    transport = GroqChatTransport("synthetic-test-token")
    result = transport({"model": "mock", "messages": []})
    assert result["choices"][0]["message"]["content"] == "ok"
    req, timeout = captured[0]
    assert req.full_url == GROQ_COMPLETIONS_URL and timeout == 30
    assert req.get_method() == "POST"
    assert b'"model": "mock"' in req.data


def test_provider_http_error_does_not_leak_response_body_or_key(monkeypatch):
    def fake_open(_req, timeout):
        raise urllib.error.HTTPError(GROQ_COMPLETIONS_URL, 429, "SECRET",
                                     {}, io.BytesIO(b"private prompt data"))
    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    with pytest.raises(GroqTransportError) as exc:
        GroqChatTransport("do-not-log-me")({"model": "mock"})
    assert str(exc.value) == "provider_http_429"
    assert "private" not in str(exc.value) and "do-not-log-me" not in str(exc.value)


def test_response_size_limited(monkeypatch):
    class Huge:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit):
            return b"x" * limit
    fake_provider(monkeypatch, lambda *_args, **_kw: Huge())
    with pytest.raises(GroqTransportError, match="provider_response_oversized"):
        GroqChatTransport("token", max_response_bytes=1024)({"model": "mock"})


def test_transport_rejects_empty_key():
    with pytest.raises(ValueError):
        GroqChatTransport("")


def test_invalid_provider_json_redacted(monkeypatch):
    class Bad:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self, _):
            return b"invalid"
    fake_provider(monkeypatch, lambda *_a, **_kw: Bad())
    with pytest.raises(GroqTransportError, match="invalid_provider_json"):
        GroqChatTransport("token")({"model": "mock"})


def test_groq_transport_redirects_rejected():
    assert _NoRedirect().redirect_request(None, None, 302, "moved", {},
                                          "https://attacker.example/") is None
