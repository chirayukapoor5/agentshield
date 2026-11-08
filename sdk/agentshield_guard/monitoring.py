"""Bounded, offline AgentShield decision monitoring. Never stores arguments."""
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from threading import RLock
import json
import re

SAFE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")

@dataclass(frozen=True)
class SecurityEvent:
    sequence: int
    timestamp: str
    tool: str
    allowed: bool
    reason: str
    severity: str

class SecurityMonitor:
    """Thread-safe audit callback: AgentShield(policy, audit=monitor)."""
    def __init__(self, *, capacity=1000, denial_threshold=3):
        if type(capacity) is not int or not 2 <= capacity <= 100000:
            raise ValueError("invalid capacity")
        if type(denial_threshold) is not int or not 2 <= denial_threshold <= capacity:
            raise ValueError("invalid denial threshold")
        self._events = deque(maxlen=capacity)
        self._lock = RLock()
        self._sequence = 0
        self._threshold = denial_threshold

    def record(self, decision):
        tool, reason, allowed = decision.tool, decision.reason, decision.allowed
        if (not isinstance(tool, str) or not SAFE.fullmatch(tool)
                or not isinstance(reason, str) or not SAFE.fullmatch(reason)
                or type(allowed) is not bool):
            raise ValueError("invalid audit metadata")
        severity = "info" if allowed else ("high" if reason == "tool_not_allowlisted" else "medium")
        with self._lock:
            self._sequence += 1
            self._events.append(SecurityEvent(
                self._sequence, datetime.now(timezone.utc).isoformat(),
                tool, allowed, reason, severity))

    __call__ = record

    def snapshot(self):
        with self._lock:
            events = list(self._events)
            total = self._sequence
        denied = [e for e in events if not e.allowed]
        groups = {}
        for e in denied:
            groups.setdefault(e.tool, []).append(e)
        incidents = [
            {"rule": "repeated_denials_in_retained_window", "severity": "high",
             "tool": tool, "count": len(matches),
             "first_sequence": matches[0].sequence,
             "last_sequence": matches[-1].sequence}
            for tool, matches in sorted(groups.items())
            if len(matches) >= self._threshold
        ]
        return {"schema_version": 1, "mode": "local_in_memory",
                "total_seen": total, "retained": len(events),
                "dropped": total - len(events),
                "summary": {"allowed": len(events) - len(denied),
                            "denied": len(denied),
                            "by_reason": dict(sorted(Counter(e.reason for e in events).items()))},
                "incidents": incidents, "events": [asdict(e) for e in events]}

    def json_report(self):
        return json.dumps(self.snapshot(), indent=2, ensure_ascii=True)

    def html_report(self):
        """Standalone static dashboard; no JavaScript or remote resources."""
        report = self.snapshot()
        columns = ("sequence", "timestamp", "tool", "allowed", "reason", "severity")
        rows = "".join("<tr>" + "".join(
            "<td>" + escape(str(e[key])) + "</td>" for key in columns
        ) + "</tr>" for e in report["events"])
        alerts = "".join(
            "<li>" + escape(i["tool"]) + ": " + str(i["count"]) +
            " denials (retained window)</li>" for i in report["incidents"]
        ) or "<li>No threshold alerts in retained window</li>"
        return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">"
                "<title>AgentShield Local Incident Dashboard</title>"
                "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem;"
                "background:#101827;color:#edf2fa}table{border-collapse:collapse;width:100%}"
                "td,th{border:1px solid #667;padding:.5rem;text-align:left}"
                "th{background:#26384e}</style></head><body>"
                "<h1>AgentShield Security Monitoring</h1>"
                "<p>Offline audit snapshot, not live telemetry or a production SIEM. "
                "No tool arguments recorded.</p>"
                "<p>Total seen: " + str(report["total_seen"]) +
                " | Retained: " + str(report["retained"]) +
                " | Dropped: " + str(report["dropped"]) +
                " | Denied (retained): " + str(report["summary"]["denied"]) + "</p>"
                "<h2>Incidents</h2><ul>" + alerts + "</ul><h2>Events</h2>"
                "<table><thead><tr>" + "".join("<th>" + escape(c) + "</th>" for c in columns) +
                "</tr></thead><tbody>" + rows + "</tbody></table></body></html>")
