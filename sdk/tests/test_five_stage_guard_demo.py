"""Tests for the actual Python AgentShield five-stage demonstration."""
from pathlib import Path
import runpy


def test_five_stage_demo_executes_real_guard_and_has_no_side_effects():
    path = Path(__file__).resolve().parents[1] / "examples" / "five_stage_guard_demo.py"
    report = runpy.run_path(str(path))["simulate"]()
    assert report["source"] == "actual_python_agentshield_guard"
    assert report["synthetic_only"] is True
    results = {x["stage"]: x for x in report["outcomes"]}
    assert len(results) == 10
    assert results["1_read"]["decision"] == "allowed"
    assert results["2_email_denied"]["reason"] == "approval_denied"
    assert results["2_email_approved"]["decision"] == "allowed"
    assert results["2_email_approved"]["result"]["delivered"] is False
    assert results["2_email_again_denied"]["reason"] == "approval_denied"
    assert results["3_delete_denied"]["reason"] == "approval_denied"
    assert results["3_delete_approved"]["result"]["real_file_touched"] is False
    assert results["4_url_denied"]["reason"] == "destination_not_allowlisted"
    assert results["4_url_allowed"]["result"]["network_requested"] is False
    assert results["5_command_denied"]["reason"] == "approval_denied"
    assert results["5_command_approved"]["result"]["real_shell_started"] is False
    assert report["state"]["reads"] == 1
    assert len(report["state"]["outbox"]) == 1
    assert report["state"]["file_present"] is False
    assert report["state"]["offline_fetches"] == 1
    assert report["state"]["toy_commands"] == 1
    assert len(report["audit"]) == 10


def test_demo_does_not_import_real_egress_or_execution_packages():
    path = Path(__file__).resolve().parents[1] / "examples" / "five_stage_guard_demo.py"
    source = path.read_text(encoding="utf-8")
    for phrase in ("import subprocess", "import requests", "import os",
                   "urllib.request", "os.system(", "subprocess.run("):
        assert phrase not in source
