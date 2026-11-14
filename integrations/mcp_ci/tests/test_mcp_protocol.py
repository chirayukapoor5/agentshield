from __future__ import annotations

import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError

from agentshield_mcp_ci.server import create_server


class FakeGitHub:
    is_fixture = True
    def list_runs(self, workflow=None, limit=10):
        return [{"id": 42, "workflow": workflow or "sdk", "branch": "research/multilingual-injection-2026", "status": "completed",
                 "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:01Z",
                 "conclusion": "success", "html_url": "https://github.com/chirayukapoor5/agentshield/actions/runs/42"}][:limit]
    def get_run(self, run_id):
        if run_id != 42:
            raise LookupError("private failure detail")
        return {"id": run_id, "workflow": "sdk", "branch": "research/multilingual-injection-2026", "status": "completed",
                "conclusion": "success", "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:01Z", "html_url": "https://github.com/chirayukapoor5/agentshield/actions/runs/42", "jobs": []}


class FakeReports:
    is_fixture = True
    def get_report(self, run_id, python_version=None):
        if run_id != 42:
            return None
        return {"schema_version": 1, "run_id": 42, "python_version": python_version or "3.12",
                "passed": 10, "failed": 1, "skipped": 0, "errors": 0, "total": 11,
                "duration_seconds": 1.2, "failed_tests": ["a" * 64], "is_fixture": True}


@pytest.mark.asyncio
async def test_protocol_discovery_and_valid_calls():
    async with Client(create_server(FakeGitHub(), FakeReports())) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {"list_ci_runs", "get_ci_run", "get_test_summary", "list_failed_tests"}
        listed = await client.call_tool("list_ci_runs", {"workflow": "sdk", "limit": 1})
        assert listed.structured_content["runs"][0]["id"] == 42
        assert listed.structured_content["is_fixture"] is True
        detail = await client.call_tool("get_ci_run", {"run_id": 42})
        assert detail.structured_content["run"]["id"] == 42
        summary = await client.call_tool("get_test_summary", {"run_id": 42, "python_version": "3.12"})
        assert summary.structured_content["report"]["failed"] == 1
        failed = await client.call_tool("list_failed_tests", {"run_id": 42, "limit": 1})
        assert failed.structured_content["failed_tests"] == ["a" * 64]


@pytest.mark.asyncio
async def test_unknown_tool_and_schema_reject_invalid_arguments():
    async with Client(create_server(FakeGitHub(), FakeReports()), raise_exceptions=False) as client:
        assert (await client.call_tool("unknown_tool", {})).is_error
        for args in ({"run_id": -1}, {"run_id": True}, {"run_id": "42"}, {"run_id": 42, "extra": "x"}):
            with pytest.raises(MCPError, match="Invalid tool arguments"):
                await client.call_tool("get_ci_run", args)
        for args in ({"limit": 0}, {"limit": 21}, {"limit": "2"}, {"workflow": "arbitrary"}):
            with pytest.raises(MCPError, match="Invalid tool arguments"):
                await client.call_tool("list_ci_runs", args)
