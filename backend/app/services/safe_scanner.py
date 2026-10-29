import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import dns.exception
import dns.resolver
from bs4 import BeautifulSoup
from fastapi import HTTPException, status

from app.core.config import settings
from app.services.verification_service import normalize_website_url

SCANNER_VERSION = "1.0"
_SCAN_SLOTS = threading.BoundedSemaphore(settings.MAX_CONCURRENT_SCANS)
_BLOCKED_METADATA_ADDRESSES = {"168.63.129.16"}
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?im)^\s*(API[_-]?KEY|SECRET(?:[_-]?KEY)?|ACCESS[_-]?TOKEN|PASSWORD)\s*[:=]\s*(['\"]?)([^\s'\"#]{8,})"
)


class ScanRequestError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class HttpResult:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    redirects: tuple[str, ...]
    truncated: bool = False
    redirect_blocked: bool = False


def _validate_target(url: str) -> tuple[str, str, int, str]:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if host is None:
            raise ScanRequestError("invalid_url", "URL has no hostname")
        try:
            origin_port = parsed.port
        except ValueError as exc:
            raise ScanRequestError("invalid_url", "URL has an invalid port") from exc
        if origin_port not in {None, 80, 443}:
            raise ScanRequestError("invalid_url", "Only standard HTTP and HTTPS ports are supported")
        normalized_origin = normalize_website_url(f"{parsed.scheme}://{parsed.netloc}")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ScanRequestError("invalid_url", "IP literal targets are not allowed")
        scheme = parsed.scheme.lower()
        port = 443 if scheme == "https" else 80
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        normalized_host = urlsplit(normalized_origin).hostname
        if normalized_host is None:
            raise ScanRequestError("invalid_url", "URL has no hostname")
        return scheme, normalized_host, port, path
    except HTTPException as exc:
        raise ScanRequestError("invalid_url", str(exc.detail)) from exc
    except ValueError as exc:
        raise ScanRequestError("invalid_url", "Redirect target was malformed") from exc


def _resolve_public_addresses(host: str, deadline: float) -> list[str]:
    resolver = dns.resolver.Resolver()
    addresses: list[str] = []
    for record_type in ("A", "AAAA"):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ScanRequestError("timeout", "DNS resolution exceeded the scan time limit")
        try:
            answers = resolver.resolve(
                host,
                record_type,
                search=False,
                lifetime=min(remaining, settings.SCAN_TIMEOUT_SECONDS),
            )
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            continue
        except dns.exception.DNSException as exc:
            raise ScanRequestError("dns_error", "DNS resolution failed") from exc
        for answer in answers:
            try:
                address = ipaddress.ip_address(answer.address)
            except ValueError as exc:
                raise ScanRequestError("dns_error", "DNS returned an invalid address") from exc
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            if (
                not address.is_global
                or address.is_reserved
                or address.is_multicast
                or address.is_unspecified
                or str(address) in _BLOCKED_METADATA_ADDRESSES
            ):
                raise ScanRequestError("prohibited_address", "DNS resolved to a non-public address")
            addresses.append(str(address))
    if not addresses:
        raise ScanRequestError("dns_error", "Hostname has no public A or AAAA records")
    return list(dict.fromkeys(addresses))


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, addresses: list[str], timeout: float):
        super().__init__(host=host, port=port, timeout=timeout)
        self._addresses = addresses

    def connect(self) -> None:
        failures: list[OSError] = []
        deadline = time.monotonic() + self.timeout
        for address in self._addresses:
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Connection attempts exceeded the request time limit")
                sock = socket.create_connection((address, self.port), remaining)
                peer = ipaddress.ip_address(sock.getpeername()[0])
                if str(peer) != address:
                    sock.close()
                    raise OSError("Connected peer did not match the validated address")
                self.sock = sock
                return
            except TimeoutError:
                raise
            except OSError as exc:
                failures.append(exc)
        raise OSError("Unable to connect to a validated public address") from failures[-1]


class _PinnedHTTPSConnection(_PinnedHTTPConnection):
    def __init__(self, host: str, port: int, addresses: list[str], timeout: float):
        super().__init__(host, port, addresses, timeout)
        self._context = ssl.create_default_context()

    def connect(self) -> None:
        failures: list[OSError] = []
        deadline = time.monotonic() + self.timeout
        for address in self._addresses:
            raw_socket = None
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Connection attempts exceeded the request time limit")
                raw_socket = socket.create_connection((address, self.port), remaining)
                peer = ipaddress.ip_address(raw_socket.getpeername()[0])
                if str(peer) != address:
                    raise OSError("Connected peer did not match the validated address")
                self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
                return
            except ssl.SSLCertVerificationError:
                if raw_socket is not None:
                    raw_socket.close()
                raise
            except TimeoutError:
                if raw_socket is not None:
                    raw_socket.close()
                raise
            except (OSError, ssl.SSLError) as exc:
                if raw_socket is not None:
                    raw_socket.close()
                failures.append(exc)
        if failures and isinstance(failures[-1], ssl.SSLError):
            raise failures[-1]
        raise OSError("Unable to connect to a validated public address") from failures[-1]


class SafeFetcher:
    def __init__(self, origin: str):
        self.origin = normalize_website_url(origin)
        self.origin_host = urlsplit(self.origin).hostname
        self.request_count = 0
        if self.origin_host is None:
            raise ScanRequestError("invalid_url", "Website URL has no hostname")

    def get(self, url: str, response_limit: int | None = None) -> HttpResult:
        current = url
        redirects: list[str] = []
        max_bytes = min(response_limit or settings.MAX_RESPONSE_BYTES, settings.MAX_RESPONSE_BYTES)
        deadline = time.monotonic() + settings.SCAN_TIMEOUT_SECONDS
        for redirect_number in range(settings.MAX_REDIRECTS + 1):
            scheme, host, port, path = _validate_target(current)
            if host != self.origin_host:
                raise ScanRequestError("redirect_blocked", "Cross-host redirects are not followed")
            self.request_count += 1
            if self.request_count > settings.MAX_SCAN_PAGES:
                raise ScanRequestError("page_limit", "Maximum scan request count reached")
            addresses = _resolve_public_addresses(host, deadline)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ScanRequestError("timeout", "Request exceeded the scan time limit")

            connection_class = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection
            connection = connection_class(host, port, addresses, remaining)
            try:
                connection.request(
                    "GET",
                    path,
                    headers={
                        "Host": host,
                        "User-Agent": "AgentShield-SafeScanner/1.0",
                        "Accept": "text/html,application/json,text/plain,*/*;q=0.1",
                        "Accept-Encoding": "identity",
                        "Connection": "close",
                    },
                )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ScanRequestError("timeout", "Request exceeded the scan time limit")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                response = connection.getresponse()
                headers = {key.lower(): value for key, value in response.getheaders()}
                if response.status in {301, 302, 303, 307, 308} and headers.get("location"):
                    destination = urljoin(current, headers["location"])
                    try:
                        _, redirect_host, _, _ = _validate_target(destination)
                    except ScanRequestError:
                        return HttpResult(current, response.status, headers, b"", tuple(redirects), redirect_blocked=True)
                    if redirect_host != self.origin_host:
                        return HttpResult(current, response.status, headers, b"", tuple(redirects), redirect_blocked=True)
                    if redirect_number >= settings.MAX_REDIRECTS:
                        raise ScanRequestError("redirect_limit", "Maximum redirect count reached")
                    redirects.append(destination)
                    current = destination
                    continue

                body = bytearray()
                truncated = False
                while len(body) <= max_bytes:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ScanRequestError("timeout", "Response exceeded the scan time limit")
                    if connection.sock is not None:
                        connection.sock.settimeout(remaining)
                    chunk = response.read(min(8192, max_bytes + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                if len(body) > max_bytes:
                    body = body[:max_bytes]
                    truncated = True
                return HttpResult(
                    current,
                    response.status,
                    headers,
                    bytes(body),
                    tuple(redirects),
                    truncated=truncated,
                )
            except ssl.SSLCertVerificationError as exc:
                raise ScanRequestError("tls_invalid", "TLS certificate validation failed") from exc
            except ssl.SSLError as exc:
                raise ScanRequestError("tls_error", "TLS negotiation failed") from exc
            except (TimeoutError, socket.timeout) as exc:
                raise ScanRequestError("timeout", "Request exceeded the scan time limit") from exc
            except dns.exception.DNSException as exc:
                raise ScanRequestError("dns_error", "DNS resolution failed") from exc
            except (OSError, http.client.HTTPException) as exc:
                raise ScanRequestError("connection_error", "Connection or HTTP response failed") from exc
            finally:
                connection.close()
        raise ScanRequestError("redirect_limit", "Maximum redirect count reached")


def _check(identifier: str, label: str, status_value: str, evidence: str, **extra: object) -> dict:
    return {
        "id": identifier,
        "label": label,
        "status": status_value,
        "evidence": evidence,
        **extra,
    }


def _unavailable(identifier: str, label: str, exc: ScanRequestError) -> dict:
    return _check(identifier, label, "unavailable", str(exc), reason=exc.kind)


def _finding(
    identifier: str,
    title: str,
    severity: str,
    affected_url: str,
    evidence: str,
    recommendation: str,
    confidence: str = "high",
) -> dict:
    return {
        "finding_type": identifier,
        "title": title,
        "severity": severity,
        "affected_url": affected_url,
        "evidence": evidence,
        "recommended_fix": recommendation,
        "confidence": confidence,
        "verification_status": "confirmed" if confidence == "high" else "inferred",
    }


def _score(checks: list[dict], included_ids: set[str]) -> tuple[float | None, dict]:
    relevant = [item for item in checks if item["id"] in included_ids and item["status"] != "unavailable"]
    if not relevant:
        return None, {"checked": 0, "total": len(included_ids)}
    passed = sum(item["status"] == "passed" for item in relevant)
    return round(100 * passed / len(relevant), 1), {"checked": len(relevant), "total": len(included_ids)}


def run_safe_scan(website_url: str) -> dict:
    if not _SCAN_SLOTS.acquire(timeout=0):
        raise ScanRequestError("concurrency_limit", "The scanner is busy. Please retry shortly.")
    try:
        return _run_safe_scan(website_url)
    finally:
        _SCAN_SLOTS.release()


def _run_safe_scan(website_url: str) -> dict:
    origin = normalize_website_url(website_url)
    host = urlsplit(origin).hostname
    if host is None:
        raise ScanRequestError("invalid_url", "Website URL has no hostname")
    fetcher = SafeFetcher(origin)
    checks: list[dict] = []
    findings: list[dict] = []

    https_result: HttpResult | None = None
    try:
        https_result = fetcher.get(f"https://{host}/")
        checks.append(_check("https", "HTTPS availability", "passed", f"HTTPS returned HTTP {https_result.status}."))
        checks.append(_check("tls_certificate", "TLS certificate", "passed", "Certificate chain and hostname validation succeeded."))
    except ScanRequestError as exc:
        if exc.kind == "tls_invalid":
            checks.append(_check("https", "HTTPS availability", "finding", "TLS connection was rejected because certificate validation failed."))
            checks.append(_check("tls_certificate", "TLS certificate", "finding", str(exc)))
            findings.append(_finding(
                "tls_certificate_invalid",
                "TLS certificate validation failed",
                "high",
                f"https://{host}/",
                str(exc),
                "Install a valid certificate for this hostname and configure a complete, trusted certificate chain.",
            ))
        else:
            checks.extend([
                _unavailable("https", "HTTPS availability", exc),
                _unavailable("tls_certificate", "TLS certificate", exc),
            ])

    http_result: HttpResult | None = None
    try:
        http_result = fetcher.get(f"http://{host}/")
        final_scheme = urlsplit(http_result.url).scheme
        if final_scheme == "https" and http_result.redirects:
            checks.append(_check("https_redirect", "HTTP to HTTPS redirect", "passed", f"HTTP redirected to HTTPS ({len(http_result.redirects)} redirect(s))."))
        elif http_result.status in {301, 302, 303, 307, 308} and http_result.redirect_blocked:
            checks.append(_check("https_redirect", "HTTP to HTTPS redirect", "unavailable", "HTTP redirected outside the verified hostname; redirect was not followed."))
        else:
            checks.append(_check("https_redirect", "HTTP to HTTPS redirect", "finding", f"HTTP returned {http_result.status} without an HTTPS redirect."))
            findings.append(_finding(
                "http_no_https_redirect",
                "HTTP does not redirect to HTTPS",
                "medium",
                http_result.url,
                f"An HTTP request returned status {http_result.status} without reaching HTTPS.",
                "Redirect HTTP requests to HTTPS and enable HSTS after confirming HTTPS works.",
            ))
    except ScanRequestError as exc:
        checks.append(_unavailable("https_redirect", "HTTP to HTTPS redirect", exc))

    if https_result is not None:
        header_rules = (
            ("strict-transport-security", "Strict-Transport-Security", "medium", "Enable HSTS on HTTPS after confirming all relevant subdomains support HTTPS."),
            ("content-security-policy", "Content-Security-Policy", "low", "Define a Content Security Policy appropriate to the site's resources."),
            ("x-content-type-options", "X-Content-Type-Options", "low", "Set X-Content-Type-Options: nosniff."),
            ("referrer-policy", "Referrer-Policy", "low", "Set a Referrer-Policy that limits unnecessary referrer disclosure."),
        )
        if 200 <= https_result.status < 300:
            missing_headers = [header for key, header, _, _ in header_rules if key not in https_result.headers]
            checks.append(_check(
                "security_headers",
                "HTTP security headers",
                "finding" if missing_headers else "passed",
                "Missing headers: " + ", ".join(missing_headers) if missing_headers else "All evaluated headers were present.",
            ))
            for key, header, severity, recommendation in header_rules:
                if key not in https_result.headers:
                    findings.append(_finding(
                        f"missing_{key.replace('-', '_')}",
                        f"Missing {header} header",
                        severity,
                        https_result.url,
                        f"The successful HTTPS response did not include the {header} header.",
                        recommendation,
                    ))
        else:
            checks.append(_check(
                "security_headers",
                "HTTP security headers",
                "unavailable",
                f"Homepage returned HTTP {https_result.status}; response headers were not used for findings.",
            ))
        if not 200 <= https_result.status < 300:
            checks.append(_check(
                "page_metadata",
                "Page metadata and structure",
                "unavailable",
                f"Homepage returned HTTP {https_result.status}; metadata was not assessed.",
            ))
        elif https_result.truncated:
            checks.append(_check("page_metadata", "Page metadata and structure", "unavailable", "HTML response exceeded the configured response limit."))
        elif (
            "text/html" not in https_result.headers.get("content-type", "").lower()
            or https_result.headers.get("content-encoding", "identity").lower() != "identity"
        ):
            checks.append(_check("page_metadata", "Page metadata and structure", "unavailable", "HTTPS response was not served as HTML."))
        else:
            soup = BeautifulSoup(https_result.body, "html.parser")
            missing = []
            if not (soup.title and soup.title.get_text(strip=True)):
                missing.append("document title")
            if not soup.find("h1"):
                missing.append("h1 heading")
            if not soup.find("main"):
                missing.append("main landmark")
            checks.append(_check(
                "page_metadata",
                "Page metadata and semantic structure",
                "finding" if missing else "passed",
                "Missing elements: " + ", ".join(missing) if missing else "Title, h1, and main landmark were observed.",
            ))
            for element in missing:
                findings.append(_finding(
                    f"missing_{element.replace(' ', '_')}",
                    f"Missing {element}",
                    "low",
                    https_result.url,
                    f"The fetched HTML did not contain a {element}.",
                    "Add descriptive page metadata and semantic HTML landmarks where appropriate.",
                ))
    else:
        checks.extend([
            _check("security_headers", "HTTP security headers", "unavailable", "No validated HTTPS response was available."),
            _check("page_metadata", "Page metadata and structure", "unavailable", "No validated HTTPS response was available."),
        ])

    robots_result: HttpResult | None = None
    sitemap_result: HttpResult | None = None
    try:
        robots_result = fetcher.get(f"https://{host}/robots.txt")
        if robots_result.status == 200:
            checks.append(_check("robots", "robots.txt accessibility", "passed", "robots.txt returned HTTP 200; its contents are not treated as a security control."))
        else:
            checks.append(_check("robots", "robots.txt accessibility", "unavailable", f"robots.txt returned HTTP {robots_result.status}."))
    except ScanRequestError as exc:
        checks.append(_unavailable("robots", "robots.txt accessibility", exc))
    try:
        sitemap_result = fetcher.get(f"https://{host}/sitemap.xml")
        if sitemap_result.status == 200:
            checks.append(_check("sitemap", "sitemap.xml accessibility", "passed", "sitemap.xml returned HTTP 200."))
        elif sitemap_result.status == 404:
            checks.append(_check("sitemap", "sitemap.xml accessibility", "finding", f"sitemap.xml returned HTTP {sitemap_result.status}; this is a discoverability observation, not a security defect."))
            findings.append(_finding(
                "sitemap_unavailable",
                "Public sitemap was not found at the standard path",
                "low",
                f"https://{host}/sitemap.xml",
                f"The standard sitemap path returned HTTP {sitemap_result.status}.",
                "If machine-readable discovery is useful for this site, publish a sitemap and reference it from robots.txt.",
                confidence="medium",
            ))
        else:
            checks.append(_check("sitemap", "sitemap.xml accessibility", "unavailable", f"sitemap.xml returned HTTP {sitemap_result.status}; availability could not be determined."))
    except ScanRequestError as exc:
        checks.append(_unavailable("sitemap", "sitemap.xml accessibility", exc))

    openapi_result: HttpResult | None = None
    openapi_paths = ("/openapi.json", "/api/openapi.json", "/swagger.json", "/openapi.yaml")
    openapi_last_status: int | None = None
    openapi_error: ScanRequestError | None = None
    for path in openapi_paths:
        try:
            candidate = fetcher.get(f"https://{host}{path}")
            openapi_last_status = candidate.status
            if candidate.status == 200 and (
                "openapi" in candidate.body[:2048].decode("utf-8", errors="ignore").lower()
                or "swagger" in candidate.body[:2048].decode("utf-8", errors="ignore").lower()
            ):
                openapi_result = candidate
                break
        except ScanRequestError as exc:
            openapi_error = exc
            break
    if openapi_result:
        checks.append(_check("openapi", "Public OpenAPI specification", "passed", f"OpenAPI/Swagger content was observed at {openapi_result.url}."))
    elif openapi_error:
        checks.append(_unavailable("openapi", "Public OpenAPI specification", openapi_error))
    else:
        checks.append(_check("openapi", "Public OpenAPI specification", "unavailable", f"No OpenAPI specification was discovered at the checked paths; last response was HTTP {openapi_last_status}."))

    sensitive_hits: list[tuple[str, str]] = []
    config_checks: list[str] = []
    config_observed = False
    for path in ("/.env", "/config.json", "/config.yaml"):
        try:
            result = fetcher.get(f"https://{host}{path}", response_limit=8192)
        except ScanRequestError as exc:
            config_checks.append(f"{path}: unavailable ({exc.kind})")
            continue
        config_checks.append(f"{path}: HTTP {result.status}")
        if result.status == 404 or (result.status == 200 and not result.truncated):
            config_observed = True
        if result.status == 200 and not result.truncated:
            text = result.body.decode("utf-8", errors="replace")
            for match in _SENSITIVE_ASSIGNMENT.finditer(text):
                sensitive_hits.append((path, match.group(1)))
    if sensitive_hits:
        affected_path, variable_name = sensitive_hits[0]
        evidence = f"{affected_path} was publicly retrievable and contained a credential-like assignment for {variable_name}; the value was not retained."
        checks.append(_check("public_config", "Public configuration indicators", "finding", evidence))
        findings.append(_finding(
            "public_credential_like_config",
            "Public configuration contains a credential-like value",
            "medium",
            f"https://{host}{affected_path}",
            evidence,
            "Remove secrets from public files, rotate any exposed credentials, and use server-side secret storage.",
            confidence="medium",
        ))
    elif config_observed:
        checks.append(_check("public_config", "Public configuration indicators", "passed", "No recognized credential-like assignments were detected in the checked paths. This check is not exhaustive."))
    else:
        checks.append(_check("public_config", "Public configuration indicators", "unavailable", "No configuration paths could be checked."))

    checks.append(_check(
        "agent_readiness",
        "Basic AI-agent discoverability indicators",
        "passed" if any(item["status"] == "passed" for item in checks if item["id"] in {"sitemap", "openapi", "page_metadata"})
        else "unavailable",
        "Evaluates only observed semantic HTML, sitemap, and public OpenAPI indicators; it does not certify agent compatibility.",
    ))

    compatibility_score, compatibility_coverage = _score(
        checks, {"page_metadata", "sitemap", "robots", "openapi", "agent_readiness"}
    )
    security_score, security_coverage = _score(
        checks, {"https", "https_redirect", "tls_certificate", "security_headers", "public_config"}
    )
    completed_checks = sum(item["status"] != "unavailable" for item in checks)
    if completed_checks == 0:
        summary = "No checks completed because the target could not be assessed. No findings were generated."
    else:
        summary = (
            f"Completed {completed_checks} of {len(checks)} checks. "
            "Scores cover only the implemented checks and are not a security certification."
        )
    return {
        "scanner_version": SCANNER_VERSION,
        "checks": checks,
        "findings": findings,
        "compatibility_score": compatibility_score,
        "security_score": security_score,
        "score_coverage": {
            "compatibility": compatibility_coverage,
            "security": security_coverage,
        },
        "summary": summary,
    }
