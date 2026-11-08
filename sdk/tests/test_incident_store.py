import pytest
from agentshield_guard.incident_store import IncidentStore

def snapshot(tool="delete", count=3):
    return {"schema_version": 1, "incidents": [
        {"tool": tool, "severity": "high", "count": count,
         "first_sequence": 1, "last_sequence": count}]}

def test_persistence_idempotence_and_status(tmp_path):
    path = tmp_path / "incidents.sqlite"
    store = IncidentStore(path)
    assert store.ingest(snapshot()) == 1
    assert store.ingest(snapshot()) == 1
    reopened = IncidentStore(path)
    items = reopened.list_incidents()
    assert len(items) == 1 and items[0]["count"] == 3
    incident_id = items[0]["id"]
    assert reopened.change_status(incident_id, "investigating")
    assert reopened.change_status(incident_id, "resolved")
    with pytest.raises(ValueError):
        reopened.change_status(incident_id, "investigating")
    assert reopened.change_status(incident_id, "open")
    assert len(reopened.history(incident_id)) == 3

def test_atomic_reject_bad_batch(tmp_path):
    store = IncidentStore(tmp_path / "db.sqlite")
    batch = snapshot()
    batch["incidents"].append({"tool": "<script>", "severity": "high",
                               "count": 1, "first_sequence": 1, "last_sequence": 1})
    with pytest.raises(ValueError):
        store.ingest(batch)
    assert store.list_incidents() == []

def test_reject_invalid_status(tmp_path):
    store = IncidentStore(tmp_path / "db.sqlite")
    store.ingest(snapshot())
    with pytest.raises(ValueError):
        store.change_status(1, "deleted")
    with pytest.raises(KeyError):
        store.change_status(99, "resolved")
