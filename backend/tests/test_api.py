from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.models import Website
from app.services import safe_scanner, verification_service
from app.services.safe_scanner import HttpResult


def demo_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "demo@agentshield.local", "password": "password123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register_website(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/websites",
        json={"name": "Owned site", "url": "https://owned.example.org"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_healthcheck(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_creates_an_isolated_organization(client: TestClient):
    payload = {
        "email": f"user-{uuid4().hex}@example.com",
        "full_name": "Test User",
        "password": "strongpass123",
    }
    registration = client.post("/api/v1/auth/register", json=payload)
    assert registration.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/websites", headers=headers).json() == []


def test_website_registration_returns_txt_challenge_and_never_marks_verified(client: TestClient):
    headers = demo_headers(client)
    created = register_website(client, headers)

    assert created["verification_status"] == "pending"
    assert created["owner_verified"] is False
    assert created["verification_dns_name"] == "_agentshield-challenge.owned.example.org"
    assert created["verification_token"]
    assert created["verification_token"] in created["verification_instructions"]


def test_scan_is_rejected_until_dns_ownership_is_verified(client: TestClient):
    headers = demo_headers(client)
    website = register_website(client, headers)

    response = client.post(f"/api/v1/websites/{website['id']}/scans", headers=headers)
    assert response.status_code == 403
    assert "Verify website ownership" in response.json()["detail"]
    assert client.get(f"/api/v1/websites/{website['id']}/scans", headers=headers).json() == []


def test_protected_workflows_require_authentication(client: TestClient):
    website = register_website(client, demo_headers(client))
    for path, method in (
        ("/api/v1/websites", "get"),
        (f"/api/v1/websites/{website['id']}/verify", "post"),
        (f"/api/v1/websites/{website['id']}/scans", "post"),
        (f"/api/v1/websites/{website['id']}/findings", "get"),
        ("/api/v1/reports", "get"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, path


def test_unverified_website_has_an_empty_scan_history(client: TestClient):
    headers = demo_headers(client)
    website = register_website(client, headers)

    scans = client.get(f"/api/v1/websites/{website['id']}/scans", headers=headers)
    assert scans.status_code == 200
    assert scans.json() == []


def test_verified_scan_persists_actual_evidence_and_report(client: TestClient, monkeypatch):
    headers = demo_headers(client)
    website = register_website(client, headers)
    monkeypatch.setattr(
        verification_service,
        "resolve_txt_records",
        lambda name: [website["verification_token"]],
    )
    verified = client.post(f"/api/v1/websites/{website['id']}/verify", headers=headers)
    assert verified.status_code == 200
    assert verified.json()["owner_verified"] is True
    assert verified.json()["verified_at"]

    class ControlledFetcher:
        def __init__(self, origin):
            self.origin = origin

        def get(self, url, response_limit=None):
            from urllib.parse import urlsplit

            path = urlsplit(url).path
            if path == "/" and url.startswith("https://"):
                return HttpResult(
                    url,
                    200,
                    {
                        "content-type": "text/html",
                        "strict-transport-security": "max-age=31536000",
                        "content-security-policy": "default-src 'self'",
                        "referrer-policy": "no-referrer",
                    },
                    b"<html><head><title>Controlled</title></head><body><main>Page</main></body></html>",
                    (),
                )
            if path == "/" and url.startswith("http://"):
                return HttpResult(
                    "https://owned.example.org/",
                    200,
                    {},
                    b"",
                    ("https://owned.example.org/",),
                )
            return HttpResult(url, 404, {}, b"", ())

    monkeypatch.setattr(safe_scanner, "SafeFetcher", ControlledFetcher)

    scan = client.post(f"/api/v1/websites/{website['id']}/scans", headers=headers)
    assert scan.status_code == 200
    assert scan.json()["status"] == "completed"
    assert scan.json()["scanner_version"] == safe_scanner.SCANNER_VERSION
    assert scan.json()["checks"]
    assert any("Missing headers: X-Content-Type-Options" in check["evidence"] for check in scan.json()["checks"])
    history = client.get(f"/api/v1/websites/{website['id']}/scans", headers=headers)
    assert history.status_code == 200
    assert any(check["id"] == "security_headers" for check in history.json()[0]["checks"])

    findings = client.get(f"/api/v1/websites/{website['id']}/findings", headers=headers)
    assert findings.status_code == 200
    header_finding = next(item for item in findings.json() if item["finding_type"] == "missing_x_content_type_options")
    assert header_finding["evidence"] == "The successful HTTPS response did not include the X-Content-Type-Options header."
    assert header_finding["verification_status"] == "confirmed"
    assert header_finding["scan_id"] == scan.json()["id"]

    report = client.post(f"/api/v1/reports/{website['id']}", headers=headers)
    assert report.status_code == 200
    assert report.json()["website_id"] == website["id"]
    assert report.json()["findings"][0]["type"] == "missing_x_content_type_options"


def test_website_urls_must_be_public_dns_origins(client: TestClient):
    headers = demo_headers(client)
    for url in (
        "http://127.0.0.1",
        "http://localhost",
        "https://service.internal",
        "https://example.org/private",
        "https://user:pass@example.org",
        "https://example.org:8443",
        "https://example.org:80",
    ):
        response = client.post(
            "/api/v1/websites",
            json={"name": "Rejected target", "url": url},
            headers=headers,
        )
        assert response.status_code == 422, url


def test_legacy_verification_flags_are_not_required_for_test_data(test_session_factory):
    db = test_session_factory()
    website = Website(
        organization_id=1,
        name="Fixture",
        url="https://owned.example.org",
        status="pending_verification",
        owner_verified=False,
        verification_status="pending",
    )
    db.add(website)
    db.commit()
    assert website.owner_verified is False
    db.close()
