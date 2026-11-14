from types import SimpleNamespace
import pytest
from agentshield_guard import AgentShield, ToolPolicy, DeniedToolCall
from agentshield_guard.monitoring import SecurityMonitor

def decision(tool="read", reason="allowlisted", allowed=True):
    return SimpleNamespace(tool=tool, reason=reason, allowed=allowed,
                           arguments={"secret": "never-log-this"})

def test_alert_and_no_argument_leak():
    monitor = SecurityMonitor(capacity=4, denial_threshold=3)
    for _ in range(3):
        monitor(decision("delete", "tool_not_allowlisted", False))
    report = monitor.snapshot()
    assert report["summary"]["denied"] == 3
    assert report["incidents"][0]["count"] == 3
    assert report["incidents"][0]["severity"] == "high"
    assert "never-log-this" not in monitor.json_report()
    assert "never-log-this" not in monitor.html_report()

def test_bounded_retention():
    monitor = SecurityMonitor(capacity=3, denial_threshold=2)
    for _ in range(5):
        monitor(decision())
    report = monitor.snapshot()
    assert [e["sequence"] for e in report["events"]] == [3, 4, 5]
    assert report["dropped"] == 2

def test_invalid_metadata_rejected_before_recording():
    monitor = SecurityMonitor()
    for item in (decision("<script>"), decision("read", "secret value"),
                 decision("read", "allowlisted", 1)):
        with pytest.raises(ValueError):
            monitor(item)
    assert monitor.snapshot()["total_seen"] == 0

def test_offline_html_dashboard():
    monitor = SecurityMonitor()
    monitor(decision())
    html = monitor.html_report()
    assert "Content-Security-Policy" in html
    assert "<script" not in html
    assert "https://" not in html

def test_invalid_config():
    for kwargs in ({"capacity": 0}, {"capacity": True},
                   {"denial_threshold": 1},
                   {"capacity": 2, "denial_threshold": 3}):
        with pytest.raises(ValueError):
            SecurityMonitor(**kwargs)

def test_real_guard_audit_callback_and_denied_handler():
    monitor = SecurityMonitor()
    calls = []
    shield = AgentShield(ToolPolicy(read_only_tools={"read"}), audit=monitor)
    wrapped = shield.wrap_registry({
        "read": lambda payload: calls.append(payload),
        "delete": lambda payload: calls.append(payload),
    })
    wrapped["read"](payload="fictional")
    with pytest.raises(DeniedToolCall):
        wrapped["delete"](payload="fictional")
    assert calls == ["fictional"]
    assert monitor.snapshot()["summary"]["denied"] == 1
    assert monitor.snapshot()["summary"]["allowed"] == 1
