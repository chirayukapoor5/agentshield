"""Typed, read-only MCP server. All public tool paths pass through AgentShield."""
import os
import inspect
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.tools.base import Tool
from mcp.types import ToolAnnotations
from agentshield_guard import DeniedToolCall
from pydantic import Field
from mcp.shared.exceptions import MCPError

from .authorization import guarded_registry
from .reports import ReportError, validate_report
from .models import (FailedTestsRequest, FailedTestsResult, ListRunsRequest, PythonVersion,
                     RunDetail, RunRequest, RunResult, RunSummary, RunsResult,
                     SummaryRequest, SummaryResult, Workflow, response)


def _exception_status(exc: Exception) -> str:
    # Translate known integration errors without returning exception text.
    status = getattr(exc, "status", None)
    if status in (404, "not_found"):
        return "not_found"
    if status in (429, "rate_limited"):
        return "rate_limited"
    if status in (401, 403, "upstream_error"):
        return "upstream_error"
    if isinstance(exc, ReportError):
        return "invalid_report"
    if isinstance(exc, DeniedToolCall):
        return "unauthorized"
    return "upstream_error"


def create_server(github: Any = None, reports: Any = None, policy: Any = None,
                  audit: Any = None) -> MCPServer:
    """Create the MCP service; dependency objects can be injected for offline use.

    Injected clients/stores must explicitly mark fixture data with is_fixture=True.
    """
    if github is None:
        from .github_client import GitHubClient
        github = GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
    if reports is None:
        from .reports import LocalReportStore
        report_dir = os.environ.get("AGENTSHIELD_REPORT_DIR")
        reports = LocalReportStore(report_dir) if report_dir else None

    def list_ci_runs(workflow: Workflow | None = None, limit: int = Field(default=10, strict=True, ge=1, le=20)) -> RunsResult:
        rows = github.list_runs(workflow=workflow.value if isinstance(workflow, Workflow) else workflow, limit=limit)
        runs = [RunSummary.model_validate(row).model_dump(mode="json") for row in rows[:limit]]
        return RunsResult.model_validate(response("ok", source="fixture" if getattr(github, "is_fixture", False) else "github",
                        is_fixture=getattr(github, "is_fixture", False), runs=runs))

    def get_ci_run(run_id: int = Field(strict=True, gt=0)) -> RunResult:
        run = github.get_run(run_id)
        run = RunDetail.model_validate(run).model_dump(mode="json")
        return RunResult.model_validate(response("ok", source="fixture" if getattr(github, "is_fixture", False) else "github",
                        is_fixture=getattr(github, "is_fixture", False), run=run))

    def get_test_summary(run_id: int = Field(strict=True, gt=0), python_version: PythonVersion | None = None) -> SummaryResult:
        python_version = python_version.value if isinstance(python_version, PythonVersion) else python_version
        report = reports.get_report(run_id, python_version) if reports is not None else None
        if report is None:
            return SummaryResult.model_validate(response("report_unavailable", source="local_report",
                            is_fixture=getattr(reports, "is_fixture", False), report=None))
        report = validate_report(report)
        if report.get("run_id") != run_id or (python_version and report.get("python_version") != python_version):
            return SummaryResult.model_validate(response("invalid_report", source="local_report", is_fixture=bool(report.get("is_fixture")), report=None))
        summary = {key: value for key, value in report.items() if key != "failed_tests"}
        return SummaryResult.model_validate(response("ok", source="fixture" if report.get("is_fixture") else "local_report",
                        is_fixture=bool(report.get("is_fixture")), report=summary))

    def list_failed_tests(run_id: int = Field(strict=True, gt=0), limit: int = Field(default=10, strict=True, ge=1, le=20)) -> FailedTestsResult:
        report = reports.get_report(run_id, None) if reports is not None else None
        if report is None:
            return FailedTestsResult.model_validate(response("report_unavailable", source="local_report",
                            is_fixture=getattr(reports, "is_fixture", False), failed_tests=[]))
        report = validate_report(report)
        if report.get("run_id") != run_id:
            return FailedTestsResult.model_validate(response("invalid_report", source="local_report", is_fixture=bool(report.get("is_fixture")), failed_tests=[]))
        ids = report["failed_tests"]
        return FailedTestsResult.model_validate(response("ok", source="fixture" if report.get("is_fixture") else "local_report",
                        is_fixture=bool(report.get("is_fixture")), failed_tests=ids[:limit]))

    raw = {"list_ci_runs": list_ci_runs, "get_ci_run": get_ci_run,
           "get_test_summary": get_test_summary, "list_failed_tests": list_failed_tests}
    guarded = guarded_registry(raw, policy=policy, audit=audit)

    # MCP's typed decorator derives JSON schemas from annotations and rejects
    # malformed arguments before invocation. Exceptions from guarded calls are
    # deliberately translated into stable envelopes with no internal details.
    request_models = {"list_ci_runs": ListRunsRequest, "get_ci_run": RunRequest,
                      "get_test_summary": SummaryRequest, "list_failed_tests": FailedTestsRequest}

    async def validate_raw_arguments(ctx: Any, call_next: Any) -> Any:
        if ctx.method == "tools/call":
            params = ctx.params if isinstance(ctx.params, dict) else {}
            name = params.get("name")
            model = request_models.get(name)
            if model is not None:
                try:
                    model.model_validate(params.get("arguments", {}))
                except Exception:
                    raise MCPError(-32602, "Invalid tool arguments") from None
        return await call_next(ctx)

    registered_tools = []
    result_models = {"list_ci_runs": RunsResult, "get_ci_run": RunResult,
                     "get_test_summary": SummaryResult, "list_failed_tests": FailedTestsResult}
    for tool_name, handler in guarded.items():
        result_model = result_models[tool_name]
        def safe_handler(_handler: Any = handler, _model: Any = result_model, **kwargs: Any) -> Any:
            try:
                return _handler(**kwargs)
            except Exception as exc:
                status = _exception_status(exc)
                return _model.model_validate(response(status, source="github" if status in {"not_found", "rate_limited", "upstream_error"} else "local_report",
                                is_fixture=False))
        safe_handler.__name__ = tool_name
        safe_handler.__signature__ = inspect.signature(handler)
        safe_handler.__annotations__ = dict(handler.__annotations__)
        safe_handler.__annotations__["return"] = result_model
        registered = Tool.from_function(safe_handler, name=tool_name,
            description=f"Read-only {tool_name.replace('_', ' ')}",
            annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                        idempotent_hint=True, open_world_hint=True),
            structured_output=True)
        registered.parameters = request_models[tool_name].model_json_schema()
        registered_tools.append(registered)
    return MCPServer("AgentShield CI Intelligence", tools=registered_tools,
                     middleware=[validate_raw_arguments])
