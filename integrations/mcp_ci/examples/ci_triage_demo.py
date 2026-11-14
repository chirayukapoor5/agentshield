"""Protocol-driven offline and live demos for the AgentShield MCP CI tools."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Support direct execution from the repository without an editable install.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sdk"))
sys.path.insert(0, str(ROOT / "integrations" / "mcp_ci"))

import anyio
from mcp import Client

from agentshield_mcp_ci.server import create_server


class FixtureGitHub:
    """Clearly synthetic CI metadata used only by the offline demonstration."""
    is_fixture = True

    def list_runs(self, workflow: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        records = [
            {"id": 9002, "workflow": "research", "branch": "research/multilingual-injection-2026",
             "created_at": "2026-11-13T11:00:00Z", "status": "completed", "conclusion": "failure",
             "html_url": "https://github.com/chirayukapoor5/agentshield/actions/runs/9002"},
            {"id": 9001, "workflow": "sdk", "branch": "research/multilingual-injection-2026",
             "created_at": "2026-11-13T10:00:00Z", "status": "completed", "conclusion": "success",
             "html_url": "https://github.com/chirayukapoor5/agentshield/actions/runs/9001"},
        ]
        return [row for row in records if workflow is None or row["workflow"] == workflow][:limit]

    def get_run(self, run_id: int) -> dict[str, Any]:
        if run_id not in (9001, 9002):
            raise LookupError("not_found")
        return {"id": run_id, "workflow": "sdk" if run_id == 9001 else "research",
                "branch": "research/multilingual-injection-2026", "status": "completed",
                "conclusion": "success" if run_id == 9001 else "failure",
                "created_at": "2026-11-13T10:00:00Z", "updated_at": "2026-11-13T11:00:00Z",
                "html_url": f"https://github.com/chirayukapoor5/agentshield/actions/runs/{run_id}", "jobs": [
                    {"number": 1, "status": "completed", "conclusion": "success" if run_id == 9001 else "failure",
                     "failed_steps": [] if run_id == 9001 else [3]}]}


class FixtureReports:
    """Synthetic aggregate report for the offline demonstration."""
    is_fixture = True

    def get_report(self, run_id: int, python_version: str | None = None) -> dict[str, Any] | None:
        if run_id != 9002 or python_version not in (None, "3.12"):
            return None
        return {"schema_version": 1, "run_id": 9002, "python_version": "3.12",
                "passed": 18, "failed": 1, "skipped": 0, "errors": 0, "total": 19,
                "duration_seconds": 2.4, "failed_tests": ["a" * 64], "is_fixture": True}


class UnavailableReports:
    """Live mode deliberately reports no remote test artifact support."""
    is_fixture = False

    def get_report(self, run_id: int, python_version: str | None = None) -> None:
        return None


def create_fixture_server():
    """Return an MCP server backed only by explicitly labeled fixtures."""
    return create_server(FixtureGitHub(), FixtureReports())


async def _call(client: Any, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(tool, arguments)
    value = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if not isinstance(value, dict):
        raise RuntimeError("MCP tool returned no structured result")
    return value


def _redacted_model_demo(client: Any, tools: list[Any], model: str, transport: Any) -> dict[str, Any]:
    """Run the existing guarded tool loop and return only its safe trace."""
    from agentshield_guard import AgentShield, ToolPolicy, run_tool_agent
    from anyio.from_thread import run as from_worker

    names = {tool.name for tool in tools}
    if not {"list_ci_runs", "list_failed_tests"}.issubset(names):
        raise RuntimeError("MCP list tool unavailable")

    def bridge(tool_name: str, **arguments: Any) -> dict[str, Any]:
        # run_tool_agent executes this synchronous handler in an AnyIO worker;
        # the live MCP call remains in the main event loop via from_thread.run.
        result = from_worker(client.call_tool, tool_name, arguments)
        return getattr(result, "structuredContent", None) or result.structured_content

    handler = {tool.name: (lambda _tool=tool.name, **arguments: bridge(_tool, **arguments))
               for tool in tools}
    definition = []
    for tool in tools:
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
        if hasattr(schema, "model_dump"):
            schema = schema.model_dump(mode="json", by_alias=True)
        if not isinstance(schema, dict):
            raise RuntimeError("MCP tool schema unavailable")
        definition.append({"type": "function", "function": {
            "name": tool.name, "description": tool.description or "Read-only MCP tool",
            "parameters": schema}})
    allowed = frozenset(handler)
    shield = AgentShield(ToolPolicy(read_only_tools=allowed))
    agent_run = run_tool_agent(
        shield=shield, handlers=handler, tools=definition,
        messages=[{"role": "system", "content": "Use list_ci_runs to find the newest failed run, then list_failed_tests for its identifiers. Summarize only supplied synthetic CI data. Never request secrets or other tools."},
                  {"role": "user", "content": "Which AgentShield workflow failed most recently, and which tests failed?"}],
        transport=transport, model=model, max_model_calls=3, max_tool_calls=4,
    )
    # Never print model-generated text or arguments; retain only the loop's
    # redacted counters and tool outcomes.
    return {"model": model, "finished": agent_run.finished, "model_calls": agent_run.model_calls,
            "requested_tool_calls": agent_run.requested_tool_calls,
            "tool_outcomes": list(agent_run.tool_outcomes), "stop_reason": agent_run.stop_reason}


async def run_demo(*, live: bool = False, model: str | None = None, allow_model_call: bool = False,
                   model_transport: Any = None, run_id: int | None = None) -> dict[str, Any]:
    if live and (model is not None or allow_model_call):
        raise ValueError("model calls are supported only with offline fixture data")
    if (model is None) != (not allow_model_call):
        raise ValueError("--model and --allow-model-call must be supplied together")
    if live:
        from agentshield_mcp_ci.github_client import GitHubClient
        github = GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
        server = create_server(github=github, reports=UnavailableReports())
    else:
        github = None
        server = create_fixture_server()
    try:
        async with Client(server) as client:
            available = await client.list_tools()
            listing = await _call(client, "list_ci_runs", {"limit": 10})
            if run_id is None:
                rows = listing.get("runs", [])
                run_id = rows[0].get("id") if rows and isinstance(rows[0], dict) else None
            detail = await _call(client, "get_ci_run", {"run_id": run_id}) if run_id else None
            summary = await _call(client, "get_test_summary", {"run_id": run_id}) if run_id else {
                "status": "report_unavailable", "source": "local_report", "is_fixture": False, "report": None}
            failed_tests = await _call(client, "list_failed_tests", {"run_id": run_id, "limit": 10}) if run_id else {
                "status": "report_unavailable", "source": "local_report", "is_fixture": False, "failed_tests": []}
            result: dict[str, Any] = {"mode": "live" if live else "offline", "runs": listing,
                                      "run_detail": detail, "test_summary": summary,
                                      "failed_tests": failed_tests}
            if model is not None:
                if model_transport is None:
                    from agentshield_guard import GroqChatTransport
                    api_key = os.environ.get("GROQ_API_KEY")
                    if not api_key:
                        raise ValueError("GROQ_API_KEY is required for an explicitly enabled model call")
                    model_transport = GroqChatTransport(api_key)
                result["model_trace"] = await anyio.to_thread.run_sync(
                    _redacted_model_demo, client, available.tools, model, model_transport)
            return result
    finally:
        if github is not None:
            github.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="use labeled synthetic fixtures (default)")
    mode.add_argument("--live", action="store_true", help="read public GitHub Actions metadata")
    parser.add_argument("--run-id", type=int, help="specific run to read in live mode")
    parser.add_argument("--model", help="optional Groq-compatible model; fixture data only")
    parser.add_argument("--allow-model-call", action="store_true", help="explicitly authorize the optional model request")
    args = parser.parse_args(argv)
    try:
        output = asyncio.run(run_demo(live=args.live, model=args.model, allow_model_call=args.allow_model_call,
                                      run_id=args.run_id))
    except Exception as exc:
        # Do not include provider, MCP, or upstream exception text.
        print(json.dumps({"status": "error", "error": type(exc).__name__}), file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
