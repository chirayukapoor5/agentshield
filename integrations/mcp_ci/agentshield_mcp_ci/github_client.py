"""Read-only, fixed-scope GitHub Actions metadata client."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

REPOSITORY = "chirayukapoor5/agentshield"
BRANCH = "research/multilingual-injection-2026"
API_ROOT = "https://api.github.com/repos/chirayukapoor5/agentshield"
WORKFLOWS = {
    "sdk": "sdk.yml",
    "research": "research.yml",
    "guard-stress": "guard-stress-10k.yml",
    "mcp-ci": "mcp-ci.yml",
}
_MAX_RESPONSE_BYTES = 1_000_000
_RUN_ID_RE = re.compile(r"^[1-9][0-9]{0,19}$")
_SAFE_CONCLUSIONS = {"success", "failure", "cancelled", "skipped", "timed_out", "action_required", "neutral", "stale", "startup_failure"}
_SAFE_STATUSES = {"queued", "in_progress", "completed", "waiting", "requested", "pending"}


class CIError(Exception):
    """Safe, status-only error intended for presentation to callers."""

    def __init__(self, status: str):
        self.status = status
        super().__init__(status)


class GitHubClient:
    """GitHub Actions reader constrained to the AgentShield repository."""

    def __init__(self, token: str | None = None, transport: httpx.BaseTransport | None = None):
        headers = {"Accept": "application/vnd.github+json", "Accept-Encoding": "identity", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            headers=headers, transport=transport, timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False, trust_env=False,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        # path is only assembled internally from the fixed routes below.
        url = API_ROOT + path
        deadline = time.monotonic() + 10
        try:
            with self._client.stream("GET", url, params=params) as response:
                if response.is_redirect:
                    raise CIError("upstream_error")
                if response.status_code == 404:
                    raise CIError("not_found")
                if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                    raise CIError("rate_limited")
                if response.status_code == 429:
                    raise CIError("rate_limited")
                if response.status_code != 200:
                    raise CIError("upstream_error")
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise CIError("upstream_error")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > _MAX_RESPONSE_BYTES or time.monotonic() > deadline:
                        raise CIError("upstream_error")
                    chunks.append(chunk)
        except CIError:
            raise
        except (httpx.HTTPError, OSError):
            raise CIError("upstream_error") from None
        try:
            body = json.loads(b"".join(chunks))
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise CIError("upstream_error") from None
        if not isinstance(body, dict):
            raise CIError("upstream_error")
        return body

    @staticmethod
    def _valid_limit(limit: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise CIError("invalid_input")
        return limit

    @staticmethod
    def _valid_run_id(run_id: int) -> str:
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0 or not _RUN_ID_RE.fullmatch(str(run_id)):
            raise CIError("invalid_input")
        return str(run_id)

    @staticmethod
    def _enum(value: Any, allowed: set[str]) -> str | None:
        return value if isinstance(value, str) and value in allowed else None

    @staticmethod
    def _run_repo_ok(run: dict[str, Any]) -> bool:
        repo = run.get("repository")
        return isinstance(repo, dict) and repo.get("full_name") == REPOSITORY

    @staticmethod
    def _run_workflow(run: dict[str, Any]) -> str | None:
        path = run.get("path")
        if not isinstance(path, str):
            return None
        return next((key for key, filename in WORKFLOWS.items() if path in (".github/workflows/" + filename, "/.github/workflows/" + filename)), None)

    def _safe_run(self, run: dict[str, Any], with_jobs: bool = False) -> dict[str, Any]:
        if not self._run_repo_ok(run) or run.get("head_branch") != BRANCH:
            raise CIError("not_found")
        workflow = self._run_workflow(run)
        if workflow is None:
            raise CIError("not_found")
        rid = run.get("id")
        if isinstance(rid, bool) or not isinstance(rid, int) or rid <= 0:
            raise CIError("upstream_error")
        out = {
            "id": rid,
            "workflow": workflow,
            "branch": BRANCH,
            "status": self._enum(run.get("status"), _SAFE_STATUSES),
            "conclusion": self._enum(run.get("conclusion"), _SAFE_CONCLUSIONS),
            "created_at": self._safe_datetime(run.get("created_at")),
            "updated_at": self._safe_datetime(run.get("updated_at")),
            "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{rid}",
        }
        if with_jobs:
            jobs = self._get(f"/actions/runs/{rid}/jobs", {"per_page": 20})
            raw_jobs = jobs.get("jobs")
            if not isinstance(raw_jobs, list):
                raise CIError("upstream_error")
            if len(raw_jobs) > 20:
                raise CIError("upstream_error")
            out["jobs_truncated"] = jobs.get("total_count", len(raw_jobs)) != len(raw_jobs)
            out["jobs"] = []
            for i, j in enumerate(raw_jobs):
                if not isinstance(j, dict) or j.get("run_id", rid) != rid:
                    raise CIError("upstream_error")
                steps = j.get("steps", [])
                if not isinstance(steps, list) or len(steps) > 100:
                    raise CIError("upstream_error")
                out["jobs"].append({"number": i + 1,
                 "status": self._enum(j.get("status"), _SAFE_STATUSES),
                 "conclusion": self._enum(j.get("conclusion"), _SAFE_CONCLUSIONS),
                 "started_at": self._safe_datetime(j.get("started_at")),
                 "completed_at": self._safe_datetime(j.get("completed_at")),
                 "failed_steps": [s["number"] for s in steps if isinstance(s, dict) and s.get("conclusion") == "failure" and type(s.get("number")) is int and 1 <= s["number"] <= 100]})
        return out

    @staticmethod
    def _safe_datetime(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return None
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return None

    def list_runs(self, workflow: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        limit = self._valid_limit(limit)
        if workflow is not None and workflow not in WORKFLOWS:
            raise CIError("invalid_input")
        params: dict[str, Any] = {"branch": BRANCH, "per_page": limit}
        route = "/actions/runs"
        if workflow is not None:
            route = "/actions/workflows/" + WORKFLOWS[workflow] + "/runs"
        data = self._get(route, params)
        runs = data.get("workflow_runs")
        if not isinstance(runs, list):
            raise CIError("upstream_error")
        result = []
        for run in runs:
            if not isinstance(run, dict) or not self._run_repo_ok(run) or run.get("head_branch") != BRANCH:
                continue
            if workflow is not None and self._run_workflow(run) != workflow:
                continue
            if self._run_workflow(run) is None:
                continue
            result.append(self._safe_run(run))
            if len(result) >= limit:
                break
        return result

    def get_run(self, run_id: int) -> dict[str, Any]:
        rid = self._valid_run_id(run_id)
        run = self._get(f"/actions/runs/{rid}")
        if run.get("id") != run_id:
            raise CIError("upstream_error")
        return self._safe_run(run, with_jobs=True)

    def list_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        rid = self._valid_run_id(run_id)
        # Verify run ownership/branch/workflow before querying its artifacts.
        run = self._get(f"/actions/runs/{rid}")
        if run.get("id") != run_id:
            raise CIError("upstream_error")
        self._safe_run(run)
        data = self._get(f"/actions/runs/{rid}/artifacts", {"per_page": 20})
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, list):
            raise CIError("upstream_error")
        safe = []
        for artifact in artifacts[:20]:
            if not isinstance(artifact, dict) or artifact.get("expired") is not False:
                continue
            aid, size = artifact.get("id"), artifact.get("size_in_bytes")
            if isinstance(aid, int) and not isinstance(aid, bool) and aid > 0 and isinstance(size, int) and not isinstance(size, bool) and size >= 0:
                safe.append({"id": aid, "size_in_bytes": size, "created_at": self._safe_datetime(artifact.get("created_at")), "expires_at": self._safe_datetime(artifact.get("expires_at"))})
        return safe
