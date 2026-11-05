import pytest
from agentshield_guard import AgentShield, DeniedToolCall, ToolPolicy


def test_unlisted_tool_fails_closed():
    shield=AgentShield(ToolPolicy())
    assert shield.decide("search").allowed is False


def test_read_only_explicit_allowlist():
    shield=AgentShield(ToolPolicy(read_only_tools=frozenset({"lookup"})))
    assert shield.decide("lookup").allowed
    assert not shield.decide("lookups").allowed


def test_no_side_effect_if_denied():
    seen=[]
    shield=AgentShield(ToolPolicy())
    fn=shield.guard("delete", lambda path: seen.append(path))
    with pytest.raises(DeniedToolCall):
        fn(path="secret")
    assert seen == []


def test_approval_required_and_exact_true():
    policy=ToolPolicy(approval_tools=frozenset({"send"}))
    assert not AgentShield(policy).decide("send").allowed
    assert not AgentShield(policy,approve=lambda *_: 1).decide("send").allowed
    assert AgentShield(policy,approve=lambda *_: True).decide("send").allowed


def test_approval_exception_denies():
    def broken(*_):
        raise RuntimeError("offline")
    assert AgentShield(ToolPolicy(approval_tools=frozenset({"send"})),approve=broken).decide("send").reason=="approval_denied"


def test_urls_are_exact_and_https_only():
    policy=ToolPolicy(read_only_tools=frozenset({"fetch"}),
                      allowed_hosts=frozenset({"docs.example.org"}),
                      url_args={"fetch": ("url",)})
    shield=AgentShield(policy)
    assert shield.decide("fetch", {"url":"https://docs.example.org/a"}).allowed
    for url in ("http://docs.example.org/a", "https://docs.example.org.evil.test/a",
                "https://docs.example.org@evil.test", "https://127.0.0.1/a",
                "https://docs.example.org:8443/a", "https://docs.example.org\\@evil.test/"):
        assert not shield.decide("fetch", {"url":url}).allowed, url


def test_missing_url_arg_fails_closed():
    shield=AgentShield(ToolPolicy(read_only_tools=frozenset({"fetch"}),
                 allowed_hosts=frozenset({"docs.example.org"}),url_args={"fetch":("url",)}))
    assert shield.decide("fetch", {}).reason=="destination_not_allowlisted"


def test_audit_failure_denies_before_execution():
    seen=[]
    def failed(_):
        raise OSError("sink unavailable")
    shield=AgentShield(ToolPolicy(read_only_tools=frozenset({"read"})),audit=failed)
    with pytest.raises(DeniedToolCall, match="audit_failed"):
        shield.guard("read",lambda:seen.append(1))()
    assert seen==[]


def test_overlapping_tool_sets_invalid():
    with pytest.raises(ValueError):
        ToolPolicy(read_only_tools=frozenset({"x"}),approval_tools=frozenset({"x"}))


def test_url_tool_must_be_allowlisted():
    with pytest.raises(ValueError):
        ToolPolicy(url_args={"fetch":("url",)})


def test_allows_explicitly_approved_execution():
    seen=[]
    guard=AgentShield(ToolPolicy(approval_tools=frozenset({"send"})),approve=lambda *_:True)
    assert guard.guard("send",lambda data:seen.append(data))(data="demo") is None
    assert seen==["demo"]


def test_wrap_registry_requires_registering_wrapped_result():
    executed=[]
    shield=AgentShield(ToolPolicy(read_only_tools=frozenset({"lookup"})))
    original={"lookup":lambda query: executed.append(query), "delete":lambda path: executed.append(path)}
    secured=shield.wrap_registry(original)
    secured["lookup"](query="safe")
    with pytest.raises(DeniedToolCall):
        secured["delete"](path="synthetic")
    assert executed==["safe"]


def test_wrap_registry_rejects_noncallables():
    shield=AgentShield(ToolPolicy())
    with pytest.raises(TypeError):
        shield.wrap_registry({"bad": "not callable"})
