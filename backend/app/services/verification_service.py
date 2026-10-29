import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit

import dns.exception
import dns.resolver
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.models import Website


def normalize_website_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Website URL must use HTTP or HTTPS.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(status_code=422, detail="Credentials, query strings, and fragments are not allowed.")
    if parsed.path not in {"", "/"}:
        raise HTTPException(status_code=422, detail="Register the website origin without a path.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Website URL has an invalid port.") from exc
    expected_port = 443 if parsed.scheme.lower() == "https" else 80
    if port not in {None, expected_port}:
        raise HTTPException(status_code=422, detail="Only standard HTTP and HTTPS ports are supported.")

    try:
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise HTTPException(status_code=422, detail="Website hostname is invalid.") from exc
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise HTTPException(status_code=422, detail="Register a DNS hostname, not an IP address.")
    if (
        "." not in host
        or len(host) > 253
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        )
        or host.endswith((".localhost", ".local", ".internal", ".invalid", ".test", ".example", ".onion"))
    ):
        raise HTTPException(status_code=422, detail="A publicly resolvable DNS hostname is required.")
    return urlunsplit((parsed.scheme.lower(), host, "", "", ""))


def verification_dns_name(website_url: str) -> str:
    hostname = urlsplit(website_url).hostname
    if hostname is None:
        raise ValueError("Website URL must contain a hostname")
    return f"_agentshield-challenge.{hostname}"


def issue_verification_token(website: Website) -> tuple[str, datetime]:
    if website.owner_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Website ownership is already verified.")
    if website.verification_locked_until and website.verification_locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Verification token issuance is temporarily locked. Try again later.",
        )
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.VERIFICATION_TOKEN_TTL_MINUTES)
    website.verification_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    website.verification_expires_at = expires_at
    website.verification_status = "pending"
    website.status = "pending_verification"
    return token, expires_at


def resolve_txt_records(name: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = min(settings.SCAN_TIMEOUT_SECONDS, 5)
    try:
        answers = resolver.resolve(name, "TXT", search=False, lifetime=resolver.lifetime)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.DNSException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DNS could not be checked right now. Please retry later.",
        ) from exc
    return [b"".join(answer.strings).decode("utf-8", errors="replace") for answer in answers]


def verify_dns_token(website: Website) -> bool:
    now = datetime.utcnow()
    if website.owner_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Website ownership is already verified.")
    if website.verification_locked_until and website.verification_locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Verification attempts are temporarily locked. Try again later.",
        )
    if website.verification_locked_until and website.verification_locked_until <= now:
        website.verification_attempts = 0
        website.verification_locked_until = None
    if not website.verification_token_hash or not website.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request a verification token before verifying this website.",
        )
    if website.verification_expires_at <= now:
        website.verification_status = "expired"
        website.verification_token_hash = None
        website.verification_expires_at = None
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Verification token expired. Request a new token.")

    expected_hash = website.verification_token_hash
    records = resolve_txt_records(verification_dns_name(website.url))
    matched = any(
        hmac.compare_digest(hashlib.sha256(record.encode("utf-8")).hexdigest(), expected_hash)
        for record in records
    )
    if matched:
        website.owner_verified = True
        website.verification_status = "verified"
        website.verified_at = now
        website.status = "verified"
        website.verification_token_hash = None
        website.verification_expires_at = None
        return True

    website.verification_attempts += 1
    website.verification_status = "pending"
    if website.verification_attempts >= settings.VERIFICATION_MAX_ATTEMPTS:
        website.verification_locked_until = now + timedelta(minutes=settings.VERIFICATION_LOCKOUT_MINUTES)
    return False
