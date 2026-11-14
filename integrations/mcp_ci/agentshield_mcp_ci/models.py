"""Stable, bounded response shapes for the MCP CI interface."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_RUN_ID = 10**20 - 1
RunID = Annotated[int, Field(strict=True, gt=0, le=MAX_RUN_ID)]
ShortTimestamp = Annotated[str, Field(max_length=40)]
RunStatus = Literal["queued", "in_progress", "completed", "waiting", "requested", "pending"]
Conclusion = Literal["success", "failure", "cancelled", "skipped", "timed_out", "action_required", "neutral", "stale", "startup_failure"]
TestID = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Workflow(str, Enum):
    sdk = "sdk"
    research = "research"
    guard_stress = "guard-stress"
    mcp_ci = "mcp-ci"


class PythonVersion(str, Enum):
    py310 = "3.10"
    py312 = "3.12"


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListRunsRequest(RequestModel):
    workflow: Literal["sdk", "research", "guard-stress", "mcp-ci"] | None = None
    limit: int = Field(default=10, strict=True, ge=1, le=20)


class RunRequest(RequestModel):
    run_id: RunID


class SummaryRequest(RunRequest):
    python_version: Literal["3.10", "3.12"] | None = None


class FailedTestsRequest(RunRequest):
    limit: int = Field(default=10, strict=True, ge=1, le=20)


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: RunID
    workflow: Workflow
    branch: Literal["research/multilingual-injection-2026"]
    status: RunStatus | None = None
    conclusion: Conclusion | None = None
    created_at: ShortTimestamp | None = None
    updated_at: ShortTimestamp | None = None
    html_url: str = Field(max_length=100, pattern=r"^https://github\.com/chirayukapoor5/agentshield/actions/runs/[1-9][0-9]{0,19}$")


class JobSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    number: int = Field(strict=True, ge=1, le=20)
    status: RunStatus | None = None
    conclusion: Conclusion | None = None
    started_at: ShortTimestamp | None = None
    completed_at: ShortTimestamp | None = None
    failed_steps: list[Annotated[int, Field(strict=True, ge=1, le=100)]] = Field(default_factory=list, max_length=100)


class RunDetail(RunSummary):
    jobs: list[JobSummary] = Field(default_factory=list, max_length=20)
    jobs_truncated: bool = False


class BaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["github", "local_report", "fixture"]
    retrieved_at: ShortTimestamp
    is_fixture: bool
    status: Literal["ok", "not_found", "rate_limited", "upstream_error", "report_unavailable", "invalid_report", "unauthorized"]


class RunsResult(BaseResult):
    runs: list[RunSummary] = Field(default_factory=list, max_length=20)


class RunResult(BaseResult):
    run: RunDetail | None = None


class TestReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    run_id: RunID
    python_version: PythonVersion
    passed: int = Field(ge=0, le=3000)
    failed: int = Field(ge=0, le=3000)
    skipped: int = Field(ge=0, le=3000)
    errors: int = Field(ge=0, le=3000)
    total: int = Field(ge=0, le=3000)
    duration_seconds: float = Field(ge=0, le=604800, allow_inf_nan=False)
    is_fixture: bool


class SummaryResult(BaseResult):
    report: TestReportSummary | None = None


class FailedTestsResult(BaseResult):
    failed_tests: list[TestID] = Field(default_factory=list, max_length=20)


def response(status: str, *, source: str = "github", is_fixture: bool = False, **data: Any) -> dict[str, Any]:
    """Build a stable response and ensure timestamps are UTC ISO-8601."""
    return {"source": source, "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "is_fixture": bool(is_fixture), "status": status, **data}
