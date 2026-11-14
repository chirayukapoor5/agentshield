"""Generate a fully offline, fictional AI-security incident dashboard.

Run: python sdk/examples/monitoring_demo.py
No network, credentials, actual files, or external tool side effects.
"""
from pathlib import Path
import json
import tempfile

from agentshield_guard import AgentShield, DeniedToolCall, ToolPolicy
from agentshield_guard.anomaly import OfflineAnomalyDetector, extract_window
from agentshield_guard.incident_store import IncidentStore
from agentshield_guard.monitoring import SecurityMonitor


def run_demo(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    monitor = SecurityMonitor(capacity=100, denial_threshold=3)
    side_effects = []
    shield = AgentShield(
        ToolPolicy(read_only_tools={"read_fixture"}),
        audit=monitor,
    )
    tools = shield.wrap_registry({
        "read_fixture": lambda: side_effects.append("fictional_read"),
        "delete_fixture": lambda: side_effects.append("fictional_delete"),
    })
    tools["read_fixture"]()
    for _ in range(4):
        try:
            tools["delete_fixture"]()
        except DeniedToolCall:
            pass
    assert side_effects == ["fictional_read"], "denied handler executed"
    snapshot = monitor.snapshot()
    store = IncidentStore(output_dir / "incidents.sqlite")
    store.ingest(snapshot)
    assert len(store.list_incidents()) == 1
    assert snapshot["summary"]["denied"] == 4
    assert extract_window(snapshot["events"]).unknown_tool_ratio == 0.8
    (output_dir / "incident-dashboard.html").write_text(
        monitor.html_report(), encoding="utf-8"
    )
    (output_dir / "audit-report.json").write_text(
        monitor.json_report(), encoding="utf-8"
    )
    return {"output": str(output_dir), "events": len(snapshot["events"]),
            "incidents": len(store.list_incidents()),
            "denied_handler_executed": False}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="agentshield-monitor-") as tmp:
        # A temporary directory is deliberately used; see docs for persistence.
        print(json.dumps(run_demo(tmp), indent=2))
        print("Demo output is temporary. Import run_demo(path) to retain reports.")
