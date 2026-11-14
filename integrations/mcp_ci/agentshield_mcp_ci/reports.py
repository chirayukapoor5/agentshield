"""Strict, bounded ingestion for sanitized AgentShield CI reports."""
from __future__ import annotations

import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

MAX_REPORT_BYTES = 256 * 1024
MAX_FAILED_TESTS = 3000
MAX_TESTS = 3000
PYTHON_VERSIONS = ("3.10", "3.12")
_KEYS = {"schema_version", "run_id", "python_version", "passed", "failed", "skipped", "errors", "total", "duration_seconds", "failed_tests", "is_fixture"}
_HASH = re.compile(r"^[0-9a-f]{64}$")


class ReportError(ValueError):
    """A safe, static report validation error (never includes input data)."""


def validate_report(report: Any) -> dict[str, Any]:
    if type(report) is not dict or set(report) != _KEYS:
        raise ReportError("invalid report schema")
    if type(report["schema_version"]) is not int or report["schema_version"] != 1:
        raise ReportError("unsupported report schema")
    if type(report["run_id"]) is not int or report["run_id"] <= 0:
        raise ReportError("invalid run identifier")
    if report["python_version"] not in PYTHON_VERSIONS:
        raise ReportError("invalid Python version")
    fields = ("passed", "failed", "skipped", "errors", "total")
    if any(type(report[k]) is not int or report[k] < 0 or report[k] > MAX_TESTS for k in fields):
        raise ReportError("invalid report counts")
    if report["total"] != sum(report[k] for k in fields[:-1]):
        raise ReportError("inconsistent report counts")
    duration = report["duration_seconds"]
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0 or duration > 7 * 24 * 3600:
        raise ReportError("invalid report duration")
    if type(report["is_fixture"]) is not bool:
        raise ReportError("invalid fixture marker")
    failed = report["failed_tests"]
    if type(failed) is not list or len(failed) > MAX_FAILED_TESTS or len(failed) != report["failed"] + report["errors"]:
        raise ReportError("invalid failed test identifiers")
    if any(type(item) is not str or not _HASH.fullmatch(item) for item in failed) or len(set(failed)) != len(failed):
        raise ReportError("invalid failed test identifiers")
    return report


def _reject_constant(_: str) -> None:
    raise ReportError("invalid JSON number")


def read_report(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes or len(data) > MAX_REPORT_BYTES:
        raise ReportError("report exceeds size limit")
    try:
        decoded = data.decode("utf-8")
        value = json.loads(decoded, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except ReportError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ReportError("invalid JSON report") from None
    return validate_report(value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReportError("duplicate JSON field")
        result[key] = value
    return result


class LocalReportStore:
    """Read reports from an operator-configured directory using fixed names.

    With no version selected, prefer 3.12 and fall back to 3.10.
    """

    def __init__(self, directory: str | os.PathLike[str]):
        self.directory = Path(directory)

    @staticmethod
    def _filename(run_id: int, python_version: str) -> str:
        if type(run_id) is not int or run_id <= 0 or python_version not in PYTHON_VERSIONS:
            raise ReportError("invalid report lookup")
        return f"run-{run_id}-py-{python_version}.json"

    def get_report(self, run_id: int, python_version: str | None = None) -> dict[str, Any] | None:
        versions = (python_version,) if python_version is not None else ("3.12", "3.10")
        candidates: list[dict[str, Any]] = []
        for version in versions:
            filename = self._filename(run_id, version)
            try:
                root = self.directory.resolve(strict=True)
                path = self.directory / filename
                info = path.lstat()
            except FileNotFoundError:
                continue
            except OSError:
                raise ReportError("report unavailable") from None
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT_BYTES:
                raise ReportError("report unavailable")
            try:
                resolved = path.resolve(strict=True)
                if resolved.parent != root:
                    raise ReportError("report unavailable")
                with path.open("rb") as stream:
                    data = stream.read(MAX_REPORT_BYTES + 1)
            except ReportError:
                raise
            except OSError:
                raise ReportError("report unavailable") from None
            report = read_report(data)
            if report["run_id"] != run_id or report["python_version"] != version:
                raise ReportError("report identity mismatch")
            candidates.append(report)
            if python_version is None:
                break
        if not candidates:
            return None
        # Prefer the current MCP integration's Python 3.12 matrix entry; fall
        # back to 3.10 when only that report is present.
        return candidates[0]
