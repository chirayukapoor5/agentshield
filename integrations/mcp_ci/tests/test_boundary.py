"""Protocol tests through the production reader and report boundary."""
import json

import httpx
import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError

from agentshield_guard import ToolPolicy
from agentshield_mcp_ci.github_client import GitHubClient, BRANCH, REPOSITORY
from agentshield_mcp_ci.server import create_server


@pytest.mark.asyncio
async def test_protocol_to_real_reader_and_unavailable_report():
    seen = []
    raw = {'id': 42, 'path': '.github/workflows/sdk.yml', 'head_branch': BRANCH,
           'repository': {'full_name': REPOSITORY}, 'status': 'completed', 'conclusion': 'failure'}
    def transport(request):
        seen.append(request)
        assert request.method == 'GET'
        if request.url.path.endswith('/jobs'):
            payload = {'jobs': [{'run_id': 42, 'steps': [{'number': 2, 'name': 'secret', 'conclusion': 'failure'}]}]}
        elif request.url.path.endswith('/42'):
            payload = raw
        else:
            assert request.url.path.endswith('/workflows/sdk.yml/runs')
            payload = {'workflow_runs': [raw]}
        return httpx.Response(200, json=payload)
    github = GitHubClient(transport=httpx.MockTransport(transport))
    async with Client(create_server(github)) as client:
        listed = await client.call_tool('list_ci_runs', {'workflow': 'sdk'})
        assert listed.structured_content['runs'][0]['id'] == 42
        detail = await client.call_tool('get_ci_run', {'run_id': 42})
        assert detail.structured_content['run']['jobs'][0]['failed_steps'] == [2]
        assert 'secret' not in str(detail)
        summary = await client.call_tool('get_test_summary', {'run_id': 42})
        assert summary.structured_content['status'] == 'report_unavailable'
        assert summary.structured_content['is_fixture'] is False
    assert len(seen) == 3
    github.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(('http_status', 'status'), [(401, 'upstream_error'), (403, 'upstream_error'),
    (404, 'not_found'), (429, 'rate_limited'), (500, 'upstream_error')])
async def test_reader_failure_remains_explicit_over_mcp(http_status, status):
    github = GitHubClient(token='credential-canary', transport=httpx.MockTransport(
        lambda _: httpx.Response(http_status, json={'message': 'credential-canary'})))
    async with Client(create_server(github)) as client:
        result = await client.call_tool('get_ci_run', {'run_id': 42})
        assert result.structured_content['status'] == status
        assert result.structured_content['run'] is None
        assert 'credential-canary' not in str(result)
    github.close()


@pytest.mark.asyncio
async def test_invalid_or_unknown_calls_never_reach_guard_or_network():
    decisions = []
    github = GitHubClient(transport=httpx.MockTransport(lambda _: pytest.fail('unexpected request')))
    async with Client(create_server(github, audit=decisions.append)) as client:
        for name, args in [('get_ci_run', {'run_id': '42'}), ('get_ci_run', {'run_id': True}),
                           ('get_ci_run', {'run_id': 10**21}),
                           ('list_ci_runs', {'workflow': 'https://evil.test/credential-canary'}),
                           ('get_test_summary', {'run_id': 42, 'path': 'credential-canary'}),
                           ('list_failed_tests', {'run_id': 42, 'limit': 21})]:
            with pytest.raises(MCPError) as exc:
                await client.call_tool(name, args)
            assert 'credential-canary' not in str(exc.value)
        assert (await client.call_tool('delete_run', {'run_id': 42})).is_error
    assert decisions == []
    github.close()


@pytest.mark.asyncio
async def test_all_four_tools_denied_before_dependencies():
    async with Client(create_server(object(), object(), policy=ToolPolicy())) as client:
        for name, args in [('list_ci_runs', {}), ('get_ci_run', {'run_id': 42}),
                           ('get_test_summary', {'run_id': 42}), ('list_failed_tests', {'run_id': 42})]:
            result = await client.call_tool(name, args)
            assert result.structured_content['status'] == 'unauthorized'


@pytest.mark.asyncio
async def test_untrusted_report_payload_is_not_emitted():
    class UnsafeReports:
        def get_report(self, *args):
            return {'run_id': 42, 'failed_tests': ['credential-canary']}
    async with Client(create_server(object(), UnsafeReports())) as client:
        for name in ('get_test_summary', 'list_failed_tests'):
            result = await client.call_tool(name, {'run_id': 42})
            assert result.structured_content['status'] == 'invalid_report'
            assert 'credential-canary' not in json.dumps(result.structured_content)
