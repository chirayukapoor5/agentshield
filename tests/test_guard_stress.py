"""Offline self-checks ensuring the 10k stress harness can detect regressions."""
from __future__ import annotations

import pytest

from agentshield_guard import AgentShield, Decision
from scripts.run_guard_stress import QUOTAS, run


def test_stress_suite_counts_and_determinism():
    first = run(cases=200, seed=20261107)
    second = run(cases=200, seed=20261107)
    assert first["executed_cases"] == 200
    assert first["passed_cases"] == 200, first["first_failures"]
    assert first["failed_cases"] == 0
    assert first["case_sequence_sha256"] == second["case_sequence_sha256"]
    assert first["category_results"] == second["category_results"]
    assert {key for key, _ in QUOTAS} == set(first["category_results"])
    assert first["real_model_calls"] == 0
    assert first["network_requests"] == 0
    assert first["is_prompt_injection_ASR"] is False


def test_suite_has_exact_10000_case_allocation():
    report = run(cases=10_000, seed=20261107)
    assert report["executed_cases"] == 10_000
    assert report["passed_cases"] == 10_000, report["first_failures"]
    assert {key: item["cases"]
            for key, item in report["category_results"].items()} == dict(QUOTAS)


def test_invalid_case_budgets_rejected():
    for count in (0, -1, True, 100_001, "10000"):
        with pytest.raises(ValueError):
            run(cases=count)
    for seed in (-1, True, 2**32, "seed"):
        with pytest.raises(ValueError):
            run(cases=10, seed=seed)


def test_harness_detects_deliberately_permissive_policy(monkeypatch):
    def insecure_decide(self, tool, arguments=None):
        return Decision(True, "unsafe_test_override", tool)

    monkeypatch.setattr(AgentShield, "decide", insecure_decide)
    report = run(cases=80, seed=7)
    assert report["failed_cases"] > 0
    assert report["category_results"]["unlisted_tool_names"]["failed"] > 0
    assert report["category_results"]["url_allowlist"]["failed"] > 0
    assert report["policy_contract_pass_fraction"] < 1
