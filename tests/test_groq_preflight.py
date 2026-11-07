"""No-network tests for Groq preflight call cap and handling."""
import urllib.error

import pytest

from scripts.groq_preflight import BASE_URL, preflight


def catalog_and_chat(url, token, payload=None, timeout=None):
    assert token == "placeholder"
    if url == BASE_URL + "/models":
        return {"data": [{"id": "test-victim"}]}
    assert payload["model"] == "test-victim"
    return {"usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5}}


def test_20_call_cap():
    output = preflight("placeholder", "test-victim", count=20,
                       sleep_seconds=0, request=catalog_and_chat, sleep=lambda _: None)
    assert output["chat_calls_attempted"] == 20
    assert output["chat_calls_succeeded"] == 20
    assert output["429_count"] == 0


def test_cannot_exceed_cap():
    with pytest.raises(ValueError, match="hard cap"):
        preflight("placeholder", "test-victim", count=21)


def test_missing_key_blocked():
    with pytest.raises(RuntimeError, match="unavailable"):
        preflight("", "test-victim")


def test_unavailable_model_does_not_call_chat():
    output = preflight("placeholder", "missing", request=catalog_and_chat)
    assert output["chat_calls_attempted"] == 0
    assert output["result"] == "model_unavailable"


def test_429_is_counted_without_retry():
    def fake(url, token, payload=None, timeout=None):
        if url.endswith("/models"):
            return {"data": [{"id": "test-victim"}]}
        raise urllib.error.HTTPError(url, 429, "too many", {}, None)
    output = preflight("placeholder", "test-victim", count=2,
                       sleep_seconds=0, request=fake, sleep=lambda _: None)
    assert output["429_count"] == 2
    assert output["chat_calls_succeeded"] == 0
