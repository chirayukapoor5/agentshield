"""Exercise the installed entrypoint over actual subprocess stdio, offline."""
import json
import sys

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.shared.exceptions import MCPError


@pytest.mark.asyncio
async def test_stdio_discovery_and_local_fixture_report(tmp_path):
    report = {"schema_version": 1, "run_id": 42, "python_version": "3.12",
              "passed": 2, "failed": 1, "skipped": 0, "errors": 0, "total": 3,
              "duration_seconds": 0.4, "failed_tests": ["b" * 64], "is_fixture": True}
    (tmp_path / 'run-42-py-3.12.json').write_text(json.dumps(report), encoding='utf-8')
    params = StdioServerParameters(command=sys.executable,
                                   args=['-m', 'agentshield_mcp_ci'],
                                   env={'AGENTSHIELD_REPORT_DIR': str(tmp_path)})
    async with Client(params, read_timeout_seconds=15) as client:
        tools = await client.list_tools()
        assert len(tools.tools) == 4
        result = await client.call_tool('get_test_summary', {'run_id': 42, 'python_version': '3.12'})
        assert result.structured_content['is_fixture'] is True
        assert result.structured_content['report']['failed'] == 1
        assert 'failed_tests' not in result.structured_content['report']
        with pytest.raises(MCPError, match='Invalid tool arguments'):
            await client.call_tool('get_ci_run', {'run_id': -1})
