# AgentShield local security monitoring (experimental)

This is an **offline, in-memory SDK audit monitor**, not a hosted SOC, live incident-management service, production SIEM, or deployed public dashboard.

```python
from agentshield_guard import AgentShield, ToolPolicy
from agentshield_guard.monitoring import SecurityMonitor

monitor = SecurityMonitor(capacity=1000, denial_threshold=3)
guard = AgentShield(ToolPolicy(read_only_tools={"read"}), audit=monitor)
tools = guard.wrap_registry({"read": lambda: "fictional document"})
tools["read"]()
with open("agentshield-incident-report.html", "w", encoding="utf-8") as out:
    out.write(monitor.html_report())
```

Open the generated HTML locally. JSON output is available through `monitor.json_report()`.

## Threat model and limitations

- The monitor records **only** timestamp, sequence, tool identifier, allow/deny decision, reason and severity; no tool arguments, prompts, destinations, tokens, or handler results.
- Tool names and reasons must match a strict 64-character ASCII identifier pattern. Invalid metadata raises an exception; when wired as the SDK audit callback, the SDK denies the guarded call before execution.
- Memory is bounded; `dropped` counts evicted events. Alert rule: at least `denial_threshold` denied calls for the same tool among **retained** events. This is not a sliding-time-window detector or a correlation engine.
- The generated HTML is static and contains no remote assets or scripts. The file is **not** served by the public showcase.
- Monitoring sees **only registered SDK-wrapped calls**. An unwrapped handler, process crash, lost memory, or malicious local host is outside its boundary.
- No durable storage, cross-process ingestion, incident acknowledgement, alert delivery, SIEM integration, authentication, access control, production scale testing, or external penetration test is provided.
- Do not upload local reports containing operational metadata to public websites without review.
- No real attack success rates, model evaluations or production protection guarantees are implied.

Verification: `python -m pytest -q sdk/tests/test_monitoring.py` with the SDK importable (e.g. `python -m pip install -e ./sdk`). This test exercises synthetic decisions and the real Python guard callback; it performs no network or paid model requests.

Release gate before calling this a *live security monitoring dashboard*: durable event ingestion, organization authorization, redaction validation, incident lifecycle, monitoring for failures, deployment-specific security review, end-to-end browser tests, and independent HTTPS verification.
