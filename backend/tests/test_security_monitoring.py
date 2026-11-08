"""Integration tests with isolated in-memory SQLite and dependency overrides."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./agentshield_test_security.db")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.core.security import get_current_active_user
from app.models.models import Organization, User

def test_security_monitoring_tenant_isolation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        org1, org2 = Organization(name="one", slug="one"), Organization(name="two", slug="two")
        db.add_all([org1, org2])
        db.flush()
        users = [
            User(organization_id=org1.id, email="one@example.invalid", full_name="One", password_hash="unused", is_active=True),
            User(organization_id=org2.id, email="two@example.invalid", full_name="Two", password_hash="unused", is_active=True),
        ]
        db.add_all(users)
        db.commit()
        ids = [u.id for u in users]
    current = {"id": ids[0]}
    def override_db():
        with Session() as db:
            yield db
    def override_user():
        with Session() as db:
            return db.get(User, current["id"])
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_user] = override_user
    try:
        with TestClient(app) as client:
            payload = {"event_id": "ev1", "tool": "delete", "reason": "tool_not_allowlisted", "allowed": False}
            assert client.post("/api/v1/security/events", json=payload).status_code == 201
            assert client.post("/api/v1/security/events", json=payload).json()["duplicate"] is True
            assert client.post("/api/v1/security/events", json={**payload, "allowed": True}).status_code == 409
            assert client.post("/api/v1/security/events", json={**payload, "event_id": "bad", "arguments": "secret"}).status_code == 422
            overview = client.get("/api/v1/security/overview").json()
            assert len(overview["events"]) == 1
            incident_id = overview["incidents"][0]["id"]
            current["id"] = ids[1]
            assert client.get("/api/v1/security/overview").json()["events"] == []
            assert client.patch(f"/api/v1/security/incidents/{incident_id}", json={"status": "resolved"}).status_code == 404
            assert client.post("/api/v1/security/events", json=payload).status_code == 201
            assert len(client.get("/api/v1/security/overview").json()["events"]) == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
