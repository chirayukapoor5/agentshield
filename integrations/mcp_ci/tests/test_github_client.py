import json

import httpx
import pytest

from agentshield_mcp_ci.github_client import BRANCH, REPOSITORY, WORKFLOWS, CIError, GitHubClient


def response(request, payload, status=200, headers=None):
    return httpx.Response(status, json=payload, headers=headers, request=request)


def run(run_id=123, workflow="sdk", branch=BRANCH, repo=REPOSITORY):
    return {
        "id": run_id,
        "path": f".github/workflows/{WORKFLOWS[workflow]}",
        "head_branch": branch,
        "repository": {"full_name": repo},
        "status": "completed",
        "conclusion": "failure",
        "created_at": "2026-11-14T00:00:00Z",
        "updated_at": "2026-11-14T00:01:00Z",
        "name": "do not expose token=private-value",
    }


def test_fixed_constants_and_list_runs_sanitizes_metadata():
    seen = []

    def handler(req):
        seen.append(req)
        assert req.method == "GET"
        assert req.url.host == "api.github.com"
        assert req.url.path == "/repos/chirayukapoor5/agentshield/actions/workflows/sdk.yml/runs"
        assert req.url.params["branch"] == BRANCH
        return response(req, {"workflow_runs": [run()]})

    client = GitHubClient(transport=httpx.MockTransport(handler))
    assert client.list_runs(workflow="sdk", limit=3) == [{
        "id": 123, "workflow": "sdk", "branch": BRANCH, "status": "completed", "conclusion": "failure",
        "created_at": "2026-11-14T00:00:00Z", "updated_at": "2026-11-14T00:01:00Z",
        "html_url": "https://github.com/chirayukapoor5/agentshield/actions/runs/123",
    }]
    assert "Authorization" not in seen[0].headers
    client.close()


def test_get_run_includes_only_job_step_numbers_and_safe_fields():
    def handler(req):
        if req.url.path.endswith("/jobs"):
            return response(req, {"jobs": [{"name": "secret job", "status": "completed", "conclusion": "failure",
                "steps": [{"name": "token=hide", "number": 4, "conclusion": "failure"}], "run_attempt": 1}]})
        return response(req, run())

    client = GitHubClient(token="never-return-this", transport=httpx.MockTransport(handler))
    result = client.get_run(123)
    rendered = json.dumps(result)
    assert result["jobs"][0]["failed_steps"] == [4]
    assert "secret" not in rendered and "never-return-this" not in rendered and "hide" not in rendered
    client.close()


def test_filters_untrusted_runs_and_only_keeps_known_workflows():
    def handler(req):
        return response(req, {"workflow_runs": [run(repo="someone/else"), run(branch="main"), run(workflow="research")]})

    client = GitHubClient(transport=httpx.MockTransport(handler))
    rows = client.list_runs()
    assert [row["workflow"] for row in rows] == ["research"]
    client.close()


@pytest.mark.parametrize("value", [0, -1, True, "1", 10**21])
def test_run_id_validation_before_network(value):
    client = GitHubClient(transport=httpx.MockTransport(lambda req: pytest.fail("network must not be called")))
    with pytest.raises(CIError) as exc:
        client.get_run(value)
    assert exc.value.status == "invalid_input"


@pytest.mark.parametrize("limit", [0, 21, True, "10"])
def test_limit_validation_before_network(limit):
    client = GitHubClient(transport=httpx.MockTransport(lambda req: pytest.fail("network must not be called")))
    with pytest.raises(CIError):
        client.list_runs(limit=limit)


def test_unknown_workflow_rejected_before_network():
    client = GitHubClient(transport=httpx.MockTransport(lambda req: pytest.fail("network must not be called")))
    with pytest.raises(CIError) as exc:
        client.list_runs(workflow="../../issues")
    assert exc.value.status == "invalid_input"


@pytest.mark.parametrize(("status", "headers", "expected"), [
    (401, {}, "upstream_error"), (403, {"X-RateLimit-Remaining": "0"}, "rate_limited"),
    (404, {}, "not_found"), (429, {}, "rate_limited"), (500, {}, "upstream_error"),
    (302, {"Location": "https://evil.test/"}, "upstream_error"),
])
def test_http_errors_are_normalized(status, headers, expected):
    client = GitHubClient(transport=httpx.MockTransport(lambda req: response(req, {"message": "token=do-not-leak"}, status, headers)))
    with pytest.raises(CIError) as exc:
        client.list_runs()
    assert exc.value.status == expected
    assert "do-not-leak" not in str(exc.value)
    client.close()


def test_oversized_response_rejected():
    def handler(req):
        return httpx.Response(200, content=b" " * 1_000_001, request=req)
    client = GitHubClient(transport=httpx.MockTransport(handler))
    with pytest.raises(CIError) as exc:
        client.list_runs()
    assert exc.value.status == "upstream_error"
    client.close()


def test_invalid_json_and_wrong_shape_are_errors():
    for raw in [b"{", b"[]"]:
        client = GitHubClient(transport=httpx.MockTransport(lambda req, raw=raw: httpx.Response(200, content=raw, request=req)))
        with pytest.raises(CIError) as exc:
            client.list_runs()
        assert exc.value.status == "upstream_error"
        client.close()


def test_artifact_metadata_omits_untrusted_names_and_expired_entries():
    def handler(req):
        if req.url.path.endswith("/artifacts"):
            return response(req, {"artifacts": [
                {"id": 9, "size_in_bytes": 42, "expired": False, "name": "token=secret", "created_at": "2026-11-13T00:00:00Z", "expires_at": "2026-12-13T00:00:00Z"},
                {"id": 10, "size_in_bytes": 12, "expired": True},
            ]})
        return response(req, run())

    client = GitHubClient(transport=httpx.MockTransport(handler))
    result = client.list_artifacts(123)
    assert result == [{"id": 9, "size_in_bytes": 42, "created_at": "2026-11-13T00:00:00Z", "expires_at": "2026-12-13T00:00:00Z"}]
    assert "secret" not in json.dumps(result)
    client.close()


def test_by_id_rejects_wrong_repo_branch_or_unknown_workflow():
    for payload in [run(repo="someone/else"), run(branch="main"), {**run(), "path": ".github/workflows/unknown.yml"}]:
        client = GitHubClient(transport=httpx.MockTransport(lambda req, payload=payload: response(req, payload)))
        with pytest.raises(CIError) as exc:
            client.get_run(123)
        assert exc.value.status == "not_found"
        client.close()


def test_response_run_identity_cannot_redirect_subsequent_request():
    seen = []
    def handler(req):
        seen.append(req.url.path)
        return response(req, run(run_id=999))
    client = GitHubClient(transport=httpx.MockTransport(handler))
    for operation in (client.get_run, client.list_artifacts):
        with pytest.raises(CIError):
            operation(123)
    assert len(seen) == 2
    assert all(path.endswith('/123') for path in seen)


def test_timeout_and_truncated_stream_redact_errors():
    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"workflow_runs":'
            raise httpx.ReadError('secret=do-not-show')
    for handler in (
        lambda req: (_ for _ in ()).throw(httpx.ReadTimeout('secret=do-not-show')),
        lambda req: httpx.Response(200, stream=Broken(), request=req),
    ):
        client = GitHubClient(transport=httpx.MockTransport(handler))
        with pytest.raises(CIError) as exc:
            client.list_runs()
        assert str(exc.value) == 'upstream_error'


@pytest.mark.parametrize('jobs', [[{}] * 21, [{'steps': [{}] * 101}], [{'run_id': 999}]])
def test_job_bounds_and_association(jobs):
    client = GitHubClient(transport=httpx.MockTransport(
        lambda req: response(req, {'jobs': jobs} if req.url.path.endswith('/jobs') else run())))
    with pytest.raises(CIError):
        client.get_run(123)


def test_jobs_truncation_is_explicit():
    client = GitHubClient(transport=httpx.MockTransport(
        lambda req: response(req, {'jobs': [{}] * 20, 'total_count': 25}
                            if req.url.path.endswith('/jobs') else run())))
    assert client.get_run(123)['jobs_truncated'] is True
