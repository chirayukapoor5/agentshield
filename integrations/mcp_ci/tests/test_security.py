from __future__ import annotations

import pytest
from mcp import Client

from agentshield_guard.guard import ToolPolicy
from agentshield_mcp_ci.server import create_server


class SideEffectGitHub:
    def __init__(self): self.calls = 0
    def list_runs(self, workflow=None, limit=10): self.calls += 1; return []
    def get_run(self, run_id): self.calls += 1; return {"run_id": run_id}


@pytest.mark.asyncio
async def test_explicit_empty_policy_denies_and_audits_before_side_effect():
    github = SideEffectGitHub()
    decisions = []
    async with Client(create_server(github, object(), policy=ToolPolicy(), audit=decisions.append),
                      raise_exceptions=False) as client:
        result = await client.call_tool("list_ci_runs", {})
    assert github.calls == 0
    assert decisions and decisions[0].allowed is False
    assert result.structured_content["status"] == "unauthorized"


@pytest.mark.asyncio
async def test_audit_failure_fails_closed_and_does_not_leak_exception():
    github = SideEffectGitHub()
    def broken_audit(_): raise RuntimeError("token=DO_NOT_LEAK")
    async with Client(create_server(github, object(), audit=broken_audit), raise_exceptions=False) as client:
        result = await client.call_tool("list_ci_runs", {})
    assert github.calls == 0
    assert result.structured_content["status"] == "unauthorized"
    assert "DO_NOT_LEAK" not in str(result)


@pytest.mark.asyncio
async def test_unexpected_upstream_error_is_masked():
    class Broken(SideEffectGitHub):
        def list_runs(self, workflow=None, limit=10): raise RuntimeError("secret token=TOPSECRET")
    async with Client(create_server(Broken(), object()), raise_exceptions=False) as client:
        result = await client.call_tool("list_ci_runs", {})
    assert result.structured_content["status"] == "upstream_error"
    assert "TOPSECRET" not in str(result)
