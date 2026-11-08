# AI + Cybersecurity roadmap and verification record

Status: **experimental, not production-ready** (2026-11-08).

## Implemented on research branch

- Python tool guard with explicit allowlists, approval gates, audit callbacks, and guarded handler registration.
- Offline security monitor (`sdk/agentshield_guard/monitoring.py`): bounded in-memory events, deny counters, repeated-denial alert, JSON export, and static local HTML incident dashboard. No prompts, arguments or credentials are collected by this monitor.
- Offline anomaly scoring (`sdk/agentshield_guard/anomaly.py`): aggregate window features and optional scikit-learn Isolation Forest with fixed seed. This is **not** a trained intrusion detector and has **no validated detection accuracy**.
- Synthetic public five-stage tool showcase, previously deployed separately through GitHub Pages. The local incident dashboard is **not** part of that public page.
- C1–C4 preregistered multilingual prompt-injection research scaffolding; no validated held-out ASR.

## Local reproduction (fictional events only)

```bash
python -m pip install -e ./sdk pytest scikit-learn
python -m pytest -q sdk/tests/test_monitoring.py sdk/tests/test_anomaly.py
python -m pytest -q sdk/tests
```

To build an offline incident report:

```python
from agentshield_guard import AgentShield, ToolPolicy
from agentshield_guard.monitoring import SecurityMonitor

monitor = SecurityMonitor(capacity=1000, denial_threshold=3)
guard = AgentShield(ToolPolicy(read_only_tools={"read"}), audit=monitor)
registered = guard.wrap_registry({"read": lambda: "fictional"})
registered["read"]()
with open("incident-report.html", "w", encoding="utf-8") as f:
    f.write(monitor.html_report())
```

To score **synthetic** baseline windows:

```python
from agentshield_guard.anomaly import OfflineAnomalyDetector, WindowFeatures
baseline = [WindowFeatures(10 + i, i / 100, 0, 0, 1 + i % 3) for i in range(20)]
detector = OfflineAnomalyDetector().fit(baseline)
print(detector.score(WindowFeatures(100, 0.8, 0.7, 0.5, 10)))
```

This only illustrates the API. Training on synthetic windows does not validate performance against real attacks.

## Unfinished before full launch

1. Run all SDK, research and frontend tests; verify current branch CI and dependency compatibility.
2. Connect authenticated, organization-scoped real telemetry ingestion with persistent retention, deduplication, access control, incident lifecycle and audit integrity.
3. Build and browser-test a real interactive security-operations UI; existing monitor HTML is a local static snapshot only.
4. Implement privacy review, secure authentication, per-tenant isolation, monitoring health, alert delivery and failure-mode handling.
5. Evaluate false-positive/false-negative behavior on permissioned, non-sensitive security datasets with a frozen holdout; no production ML effectiveness claim until verified.
6. Review deployment, check unauthenticated HTTPS for the exact published assets, and independently security-test before describing any production guarantees.

Do not merge draft PR #1, publish social claims of completion, or use secrets/paid model APIs to perform these steps without explicit approval.
