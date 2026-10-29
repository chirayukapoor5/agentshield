import hashlib
import http.client
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit

import dns.resolver
import pytest

from app.core.config import settings
from app.models.models import Agent, Finding, Report, Scan, Website
from app.services import safe_scanner, scan_service, verification_service
from app.services.safe_scanner import HttpResult, SafeFetcher, ScanRequestError


def _register_site(client, headers):
    response = client.post(
        "/api/v1/websites",
        json={"name": "Tenant site", "url": "https://owned.example.org"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _headers_for_user(client, email="demo@agentshield.local", password="password123"):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_invalid_dns_txt_does_not_verify_and_records_attempt(client, monkeypatch):
    headers = _headers_for_user(client)
    site = _register_site(client, headers)
    monkeypatch.setattr(verification_service, "resolve_txt_records", lambda name: ["not-the-token"])

    response = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    assert response.status_code == 400
    website = client.get(f"/api/v1/websites/{site['id']}", headers=headers).json()
    assert website["owner_verified"] is False
    assert website["verification_status"] == "pending"

    events = client.get("/api/v1/audit-events", headers=headers).json()
    assert any(event["event_type"] == "website.verification_attempt" for event in events)


def test_valid_dns_txt_verifies_once_and_clears_stored_token(client, monkeypatch, test_session_factory, caplog):
    headers = _headers_for_user(client)
    site = _register_site(client, headers)
    token = site["verification_token"]
    db = test_session_factory()
    website = db.query(Website).filter_by(id=site["id"]).one()
    assert website.verification_token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert website.verification_token_hash != token
    db.close()
    monkeypatch.setattr(verification_service, "resolve_txt_records", lambda name: [token])

    response = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    assert response.status_code == 200
    assert response.json()["verification_status"] == "verified"
    assert response.json()["verified_at"]
    assert token not in response.text
    assert token not in caplog.text
    assert token not in str(client.get("/api/v1/audit-events", headers=headers).json())

    db = test_session_factory()
    website = db.query(Website).filter_by(id=site["id"]).one()
    assert website.verification_token_hash is None
    assert website.verification_expires_at is None
    assert website.verification_token_hash != token
    db.close()

    reuse = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    assert reuse.status_code == 409


def test_expired_dns_token_is_invalidated_and_audited(client, monkeypatch, test_session_factory):
    headers = _headers_for_user(client)
    site = _register_site(client, headers)
    db = test_session_factory()
    website = db.query(Website).filter_by(id=site["id"]).one()
    website.verification_expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    db.close()
    monkeypatch.setattr(verification_service, "resolve_txt_records", lambda name: [site["verification_token"]])

    response = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    assert response.status_code == 410
    website_response = client.get(f"/api/v1/websites/{site['id']}", headers=headers).json()
    assert website_response["verification_status"] == "expired"
    assert website_response["owner_verified"] is False


def test_dns_verification_attempts_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "VERIFICATION_MAX_ATTEMPTS", 2)
    headers = _headers_for_user(client)
    site = _register_site(client, headers)
    monkeypatch.setattr(verification_service, "resolve_txt_records", lambda name: [])

    first = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    second = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    third = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    assert first.status_code == 400
    assert second.status_code == 429
    assert third.status_code == 429


def test_verification_dns_outage_is_reported_without_consuming_attempt(client, monkeypatch, test_session_factory):
    headers = _headers_for_user(client)
    site = _register_site(client, headers)

    def unavailable(name):
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="DNS unavailable")

    monkeypatch.setattr(verification_service, "resolve_txt_records", unavailable)
    response = client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers)
    assert response.status_code == 503

    db = test_session_factory()
    assert db.query(Website).filter_by(id=site["id"]).one().verification_attempts == 0
    db.close()


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "169.254.169.254",
        "168.63.129.16",
        "192.168.1.2",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
    ],
)
def test_dns_resolution_blocks_non_public_ipv4_and_ipv6(address, monkeypatch):
    class FakeResolver:
        def resolve(self, host, record_type, **kwargs):
            if record_type == "A":
                return [SimpleNamespace(address=address)]
            raise dns.resolver.NoAnswer()

    monkeypatch.setattr(safe_scanner.dns.resolver, "Resolver", FakeResolver)
    with pytest.raises(ScanRequestError, match="non-public"):
        safe_scanner._resolve_public_addresses("public.example.org", time.monotonic() + 5)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "169.254.169.254",
        "168.63.129.16",
        "192.168.1.2",
        "240.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
    ],
)
def test_prohibited_dns_answers_are_blocked_before_socket_creation(address, monkeypatch):
    class FakeResolver:
        def resolve(self, host, record_type, **kwargs):
            if record_type == "A":
                return [SimpleNamespace(address=address)]
            raise dns.resolver.NoAnswer()

    connection_attempts = []
    monkeypatch.setattr(safe_scanner.dns.resolver, "Resolver", FakeResolver)
    monkeypatch.setattr(
        safe_scanner.socket,
        "create_connection",
        lambda *args, **kwargs: connection_attempts.append((args, kwargs)),
    )

    fetcher = SafeFetcher("https://owned.example.org")
    with pytest.raises(ScanRequestError, match="non-public"):
        fetcher.get("https://owned.example.org/")
    assert connection_attempts == []


def test_private_dns_answer_never_reaches_a_controlled_local_server(monkeypatch):
    class CountingHandler(BaseHTTPRequestHandler):
        requests = 0

        def do_GET(self):
            type(self).requests += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), CountingHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class LocalhostResolver:
        def resolve(self, host, record_type, **kwargs):
            if record_type == "A":
                return [SimpleNamespace(address=server.server_address[0])]
            raise dns.resolver.NoAnswer()

    connection_attempts = []
    monkeypatch.setattr(safe_scanner.dns.resolver, "Resolver", LocalhostResolver)
    monkeypatch.setattr(
        safe_scanner.socket,
        "create_connection",
        lambda *args, **kwargs: connection_attempts.append((args, kwargs)),
    )
    try:
        with pytest.raises(ScanRequestError, match="non-public"):
            SafeFetcher("https://owned.example.org").get("https://owned.example.org/")
        assert connection_attempts == []
        assert CountingHandler.requests == 0
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_dns_resolution_rejects_mixed_public_and_private_answers(monkeypatch):
    class FakeResolver:
        def resolve(self, host, record_type, **kwargs):
            if record_type == "A":
                return [
                    SimpleNamespace(address="8.8.8.8"),
                    SimpleNamespace(address="10.0.0.4"),
                ]
            raise dns.resolver.NoAnswer()

    monkeypatch.setattr(safe_scanner.dns.resolver, "Resolver", FakeResolver)
    with pytest.raises(ScanRequestError, match="non-public"):
        safe_scanner._resolve_public_addresses("public.example.org", time.monotonic() + 5)


class FakeResponse:
    def __init__(self, status: int, headers: dict[str, str] | None = None, body: bytes = b""):
        self.status = status
        self._headers = headers or {}
        self._body = body
        self._offset = 0

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self._headers.items())

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class FakeConnection(http.client.HTTPConnection):
    def __init__(self, response: FakeResponse | None, error: Exception | None = None) -> None:
        super().__init__("owned.example.org", timeout=1)
        self.response = response
        self.error = error
        self.requested = []

    def request(self, method: str, path: str, headers: dict[str, str]) -> None:
        if self.error:
            raise self.error
        self.requested.append((method, path, headers))

    def getresponse(self) -> FakeResponse:
        assert self.response is not None
        return self.response

    def close(self) -> None:
        return None


def test_pinned_fetcher_revalidates_same_host_redirect_and_caps_bytes(monkeypatch):
    responses = [
        FakeResponse(301, {"Location": "https://owned.example.org/next"}),
        FakeResponse(200, {"Content-Type": "text/plain"}, b"abcdefghij"),
    ]
    resolved = []
    connections = []

    def resolve(host: str, deadline: float) -> list[str]:
        resolved.append(host)
        return ["8.8.8.8"]

    def make_connection(
        scheme: str,
        host: str,
        port: int,
        addresses: list[str],
        timeout: float,
    ) -> FakeConnection:
        assert addresses == ["8.8.8.8"]
        connection = FakeConnection(responses.pop(0))
        connections.append(connection)
        return connection

    monkeypatch.setattr(safe_scanner, "_resolve_public_addresses", resolve)
    monkeypatch.setattr(
        safe_scanner,
        "_PinnedHTTPConnection",
        lambda host, port, addresses, timeout: make_connection("http", host, port, addresses, timeout),
    )
    monkeypatch.setattr(
        safe_scanner,
        "_PinnedHTTPSConnection",
        lambda host, port, addresses, timeout: make_connection("https", host, port, addresses, timeout),
    )
    fetcher = SafeFetcher("https://owned.example.org")
    response = fetcher.get("http://owned.example.org/", response_limit=4)

    assert resolved == ["owned.example.org", "owned.example.org"]
    assert len(connections) == 2
    assert response.url == "https://owned.example.org/next"
    assert response.redirects == ("https://owned.example.org/next",)
    assert response.body == b"abcd"
    assert response.truncated is True


def test_pinned_fetcher_does_not_follow_redirect_to_metadata_ip(monkeypatch):
    connection_count = 0

    def make_connection(
        scheme: str,
        host: str,
        port: int,
        addresses: list[str],
        timeout: float,
    ) -> FakeConnection:
        nonlocal connection_count
        connection_count += 1
        return FakeConnection(FakeResponse(
            302,
            {"Location": "http://169.254.169.254/latest/meta-data/"},
        ))

    monkeypatch.setattr(safe_scanner, "_resolve_public_addresses", lambda host, deadline: ["8.8.8.8"])
    monkeypatch.setattr(
        safe_scanner,
        "_PinnedHTTPSConnection",
        lambda host, port, addresses, timeout: make_connection("https", host, port, addresses, timeout),
    )
    fetcher = SafeFetcher("https://owned.example.org")
    result = fetcher.get("https://owned.example.org/")
    assert result.redirect_blocked is True
    assert connection_count == 1


def test_pinned_http_connection_connects_to_the_validated_ip(monkeypatch):
    observed = {}

    class FakeSocket:
        def getpeername(self):
            return ("8.8.8.8", 80)

        def close(self):
            return None

    def connect(address, timeout=None, source_address=None):
        observed["address"] = address[0]
        observed["port"] = address[1]
        return FakeSocket()

    monkeypatch.setattr(safe_scanner.socket, "create_connection", connect)
    connection = safe_scanner._PinnedHTTPConnection(
        "owned.example.org",
        80,
        ["8.8.8.8"],
        2,
    )
    connection.connect()
    connection.close()

    assert observed == {"address": "8.8.8.8", "port": 80}


def test_dns_rebinding_to_private_ip_is_blocked_on_redirect(monkeypatch):
    resolve_count = 0
    connection_count = 0

    def resolve(host: str, deadline: float) -> list[str]:
        nonlocal resolve_count
        resolve_count += 1
        if resolve_count == 1:
            return ["8.8.8.8"]
        raise ScanRequestError("prohibited_address", "DNS resolved to a non-public address")

    def make_connection(
        scheme: str,
        host: str,
        port: int,
        addresses: list[str],
        timeout: float,
    ) -> FakeConnection:
        nonlocal connection_count
        connection_count += 1
        return FakeConnection(FakeResponse(
            302,
            {"Location": "https://owned.example.org/after-redirect"},
        ))

    monkeypatch.setattr(safe_scanner, "_resolve_public_addresses", resolve)
    monkeypatch.setattr(
        safe_scanner,
        "_PinnedHTTPSConnection",
        lambda host, port, addresses, timeout: make_connection("https", host, port, addresses, timeout),
    )
    fetcher = SafeFetcher("https://owned.example.org")
    with pytest.raises(ScanRequestError, match="non-public"):
        fetcher.get("https://owned.example.org/")
    assert resolve_count == 2
    assert connection_count == 1


def test_pinned_fetcher_surfaces_timeout(monkeypatch):
    def make_connection(
        scheme: str,
        host: str,
        port: int,
        addresses: list[str],
        timeout: float,
    ) -> FakeConnection:
        return FakeConnection(None, TimeoutError())

    monkeypatch.setattr(safe_scanner, "_resolve_public_addresses", lambda host, deadline: ["8.8.8.8"])
    monkeypatch.setattr(
        safe_scanner,
        "_PinnedHTTPSConnection",
        lambda host, port, addresses, timeout: make_connection("https", host, port, addresses, timeout),
    )
    fetcher = SafeFetcher("https://owned.example.org")
    with pytest.raises(ScanRequestError) as error:
        fetcher.get("https://owned.example.org/")
    assert error.value.kind == "timeout"


def test_scanner_generates_only_evidence_backed_findings_and_unavailable_checks(monkeypatch):
    class ScriptedFetcher:
        def __init__(self, origin):
            self.host = urlsplit(origin).hostname

        def get(self, url, response_limit=None):
            path = urlsplit(url).path
            if path == "/" and url.startswith("https://"):
                return HttpResult(
                    url,
                    200,
                    {"content-type": "text/html"},
                    b"<html><head><title>Example</title></head><body><h1>Welcome</h1></body></html>",
                    (),
                )
            if path == "/" and url.startswith("http://"):
                raise ScanRequestError("timeout", "Request exceeded the scan time limit")
            if path == "/robots.txt":
                return HttpResult(url, 404, {}, b"", ())
            if path == "/sitemap.xml":
                return HttpResult(url, 404, {}, b"", ())
            if path == "/.env":
                return HttpResult(
                    url,
                    200,
                    {"content-type": "text/plain"},
                    b"SECRET_KEY=this-is-a-placeholder-secret-value",
                    (),
                )
            if path in {"/config.json", "/config.yaml"}:
                return HttpResult(url, 404, {}, b"", ())
            return HttpResult(url, 404, {}, b"", ())

    monkeypatch.setattr(safe_scanner, "SafeFetcher", ScriptedFetcher)
    result = safe_scanner.run_safe_scan("https://owned.example.org")

    checks = {item["id"]: item for item in result["checks"]}
    assert checks["https_redirect"]["status"] == "unavailable"
    assert checks["page_metadata"]["status"] == "finding"
    assert checks["sitemap"]["status"] == "finding"
    assert checks["robots"]["status"] == "unavailable"
    assert checks["public_config"]["status"] == "finding"
    assert result["security_score"] is not None
    assert result["score_coverage"]["security"]["checked"] < result["score_coverage"]["security"]["total"]

    config_finding = next(item for item in result["findings"] if item["finding_type"] == "public_credential_like_config")
    assert "SECRET_KEY" in config_finding["evidence"]
    assert "this-is-a-placeholder-secret-value" not in config_finding["evidence"]


def test_unavailable_hostname_never_creates_a_fabricated_finding(monkeypatch):
    class UnavailableFetcher:
        def __init__(self, origin):
            pass

        def get(self, url, response_limit=None):
            raise ScanRequestError("dns_error", "Hostname has no public A or AAAA records")

    monkeypatch.setattr(safe_scanner, "SafeFetcher", UnavailableFetcher)
    result = safe_scanner.run_safe_scan("https://owned.example.org")
    assert result["findings"] == []
    assert all(check["status"] == "unavailable" for check in result["checks"] if check["id"] not in {"agent_readiness"})


def test_http_error_is_recorded_as_unavailable_not_an_html_finding(monkeypatch):
    class ErrorFetcher:
        def __init__(self, origin):
            pass

        def get(self, url, response_limit=None):
            path = urlsplit(url).path
            if path == "/" and url.startswith("https://"):
                return HttpResult(url, 503, {"content-type": "text/html"}, b"<html>failure</html>", ())
            if path == "/" and url.startswith("http://"):
                return HttpResult(url, 503, {}, b"", ())
            return HttpResult(url, 404, {}, b"", ())

    monkeypatch.setattr(safe_scanner, "SafeFetcher", ErrorFetcher)
    result = safe_scanner.run_safe_scan("https://owned.example.org")
    checks = {item["id"]: item for item in result["checks"]}
    assert checks["page_metadata"]["status"] == "unavailable"
    assert "HTTP 503" in checks["page_metadata"]["evidence"]
    assert not any(
        item["finding_type"] in {"missing_document_title", "missing_h1_heading", "missing_main_landmark"}
        for item in result["findings"]
    )


def test_failed_scan_is_persisted_without_claiming_success(client, monkeypatch):
    headers = _headers_for_user(client)
    site = _register_site(client, headers)
    token = site["verification_token"]
    monkeypatch.setattr(verification_service, "resolve_txt_records", lambda name: [token])
    assert client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers).status_code == 200
    monkeypatch.setattr(
        scan_service,
        "run_safe_scan",
        lambda url: (_ for _ in ()).throw(ScanRequestError("dns_error", "No public DNS records")),
    )

    result = client.post(f"/api/v1/websites/{site['id']}/scans", headers=headers).json()
    assert result["status"] == "failed"
    assert result["security_score"] is None
    assert result["checks"][0]["status"] == "unavailable"
    assert client.get(f"/api/v1/websites/{site['id']}/findings", headers=headers).json() == []


def test_scan_with_no_evaluable_checks_is_persisted_as_failed(client, monkeypatch):
    headers = _headers_for_user(client)
    site = _register_site(client, headers)
    monkeypatch.setattr(verification_service, "resolve_txt_records", lambda name: [site["verification_token"]])
    assert client.post(f"/api/v1/websites/{site['id']}/verify", headers=headers).status_code == 200

    class UnavailableFetcher:
        def __init__(self, origin):
            pass

        def get(self, url, response_limit=None):
            raise ScanRequestError("dns_error", "Hostname has no public A or AAAA records")

    monkeypatch.setattr(safe_scanner, "SafeFetcher", UnavailableFetcher)
    response = client.post(f"/api/v1/websites/{site['id']}/scans", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["security_score"] is None
    assert response.json()["compatibility_score"] is None
    assert response.json()["checks"]
    assert all(check["status"] == "unavailable" for check in response.json()["checks"])


def test_cross_tenant_resources_are_not_accessible(client, test_session_factory):
    owner_headers = _headers_for_user(client)
    site = _register_site(client, owner_headers)
    db = test_session_factory()
    scan = Scan(
        website_id=site["id"],
        status="completed",
        scanner_version="1.0",
        compatibility_score=75,
        security_score=50,
        check_results={"checks": []},
        summary="controlled test scan",
    )
    db.add(scan)
    db.flush()
    db.add(Finding(
        website_id=site["id"],
        scan_id=scan.id,
        finding_type="test",
        severity="low",
        title="Test evidence",
        category="test",
        description="Test evidence",
        evidence="Controlled fixture",
        confidence="high",
        verification_status="confirmed",
        is_confirmed=True,
        scanner_version="1.0",
        detected_at=datetime.utcnow(),
    ))
    db.add(Report(
        organization_id=1,
        website_id=site["id"],
        format="json",
        file_name="test.json",
        summary="{}",
    ))
    agent = Agent(
        organization_id=1,
        name="Owner agent",
        api_key_hash="not-a-real-credential",
        permissions={},
        is_active=True,
    )
    db.add(agent)
    db.commit()
    scan_id = scan.id
    agent_id = agent.id
    db.close()

    other_email = f"other-{hashlib.sha256(site['verification_token'].encode()).hexdigest()[:10]}@example.org"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "full_name": "Other Tenant", "password": "otherpass123"},
    )
    assert registered.status_code == 201
    other_headers = _headers_for_user(client, other_email, "otherpass123")

    assert client.get(f"/api/v1/websites/{site['id']}", headers=other_headers).status_code == 404
    assert client.post(f"/api/v1/websites/{site['id']}/scans", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/websites/{site['id']}/scans", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/websites/{site['id']}/findings", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/websites/{site['id']}/reports", headers=other_headers).status_code == 404
    assert client.post(f"/api/v1/reports/{site['id']}", headers=other_headers).status_code == 404
    assert client.get("/api/v1/reports", headers=other_headers).json() == []
    assert client.get(f"/api/v1/agents/{agent_id}", headers=other_headers).status_code == 404
    policy = client.post(
        "/api/v1/policies",
        json={
            "name": "Cross-tenant policy",
            "effect": "deny",
            "decision_mode": "enforce",
            "rules": {},
            "website_id": site["id"],
        },
        headers=other_headers,
    )
    assert policy.status_code == 404
    assert scan_id > 0
    other_events = client.get("/api/v1/audit-events", headers=other_headers).json()
    assert not any(event["resource_id"] == str(site["id"]) for event in other_events)
