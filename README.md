from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_and_login():
    payload = {"email": "user@example.com", "full_name": "Test User", "password": "strongpass123"}
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    login = client.post("/api/v1/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token


def test_create_website_and_scan():
    auth = client.post(
        "/api/v1/auth/login",
        data={"username": "demo@agentshield.local", "password": "password123"},
    )
    token = auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    website = client.post(
        "/api/v1/websites",
        json={"name": "Public docs", "url": "https://example.com"},
        headers=headers,
    )
    assert website.status_code == 201
    website_id = website.json()["id"]

    scan = client.post(f"/api/v1/websites/{website_id}/scans", headers=headers)
    assert scan.status_code == 200
    assert scan.json()["status"] == "completed"


def test_agent_policy_and_audit_endpoints():
    auth = client.post(
        "/api/v1/auth/login",
        data={"username": "demo@agentshield.local", "password": "password123"},
    )
    token = auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    agents = client.get("/api/v1/agents", headers=headers)
    assert agents.status_code == 200

    policies = client.get("/api/v1/policies", headers=headers)
    assert policies.status_code == 200

    audit = client.get("/api/v1/audit-events", headers=headers)
    assert audit.status_code == 200

