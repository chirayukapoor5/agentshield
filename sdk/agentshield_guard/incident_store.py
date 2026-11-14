"""Local SQLite incident lifecycle; trusted offline use only, not a public API."""
import sqlite3
from datetime import datetime, timezone
from threading import RLock

STATUSES = {"open", "investigating", "resolved"}

class IncidentStore:
    def __init__(self, path):
        self.path = str(path)
        self.lock = RLock()
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY, tool TEXT UNIQUE NOT NULL,
                severity TEXT NOT NULL, count INTEGER NOT NULL,
                first_sequence INTEGER NOT NULL, last_sequence INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open', updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY, incident_id INTEGER NOT NULL,
                previous TEXT NOT NULL, current TEXT NOT NULL,
                changed_at TEXT NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def ingest(self, snapshot):
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
            raise ValueError("invalid snapshot")
        incidents = snapshot.get("incidents")
        if not isinstance(incidents, list) or len(incidents) > 10000:
            raise ValueError("invalid batch")
        rows = []
        for incident in incidents:
            if not isinstance(incident, dict):
                raise ValueError("invalid incident")
            tool, severity = incident.get("tool"), incident.get("severity")
            count, first, last = (incident.get(k) for k in ("count", "first_sequence", "last_sequence"))
            if (not isinstance(tool, str) or not 1 <= len(tool) <= 64
                    or not tool.isascii() or not all(c.isalnum() or c in "_.-" for c in tool)
                    or severity not in {"low", "medium", "high", "critical"}
                    or any(type(v) is not int for v in (count, first, last))
                    or count < 1 or first < 1 or last < first):
                raise ValueError("invalid incident fields")
            rows.append((tool, severity, count, first, last))
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self.connect() as db:
            for tool, severity, count, first, last in rows:
                db.execute("""INSERT INTO incidents(tool,severity,count,first_sequence,last_sequence,updated_at)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(tool) DO UPDATE SET
                    severity=excluded.severity,
                    count=MAX(incidents.count,excluded.count),
                    first_sequence=MIN(incidents.first_sequence,excluded.first_sequence),
                    last_sequence=MAX(incidents.last_sequence,excluded.last_sequence),
                    updated_at=excluded.updated_at""", (tool,severity,count,first,last,now))
        return len(rows)

    def list_incidents(self):
        with self.lock, self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT 1000")]

    def change_status(self, incident_id, status):
        if type(incident_id) is not int or incident_id < 1 or status not in STATUSES:
            raise ValueError("invalid transition")
        with self.lock, self.connect() as db:
            row = db.execute("SELECT status FROM incidents WHERE id=?", (incident_id,)).fetchone()
            if row is None:
                raise KeyError("incident not found")
            previous = row[0]
            if previous == status:
                return False
            if previous == "resolved" and status != "open":
                raise ValueError("reopen resolved incident first")
            now = datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE incidents SET status=?,updated_at=? WHERE id=?", (status,now,incident_id))
            db.execute("INSERT INTO history(incident_id,previous,current,changed_at) VALUES(?,?,?,?)",
                       (incident_id,previous,status,now))
            return True

    def history(self, incident_id):
        if type(incident_id) is not int or incident_id < 1:
            raise ValueError("invalid incident id")
        with self.lock, self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute(
                "SELECT * FROM history WHERE incident_id=? ORDER BY id", (incident_id,))]
