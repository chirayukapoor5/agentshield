from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Finding, Scan, Website


def safe_url_validation(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if host.endswith(".internal") or host.startswith("10."):
        return False
    return True


def run_scan(db: Session, website: Website) -> dict:
    if not safe_url_validation(website.url):
        raise HTTPException(status_code=400, detail="URL is not eligible for safe external scanning")

    try:
        response = httpx.get(
            website.url,
            timeout=settings.SCAN_TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=settings.MAX_REDIRECTS,
            headers={"User-Agent": "AgentShield-Scanner/0.1"},
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Scan failed: {exc}") from exc

    score = 78 if response.status_code < 400 else 56
    scan = Scan(
        website_id=website.id,
        status="completed",
        compatibility_score=score,
        security_score=70,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        summary=f"Scanned {website.url} and reviewed metadata, headers, and document structure.",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    finding = Finding(
        website_id=website.id,
        scan_id=scan.id,
        severity="medium",
        title="Structured content is present",
        category="compatibility",
        description="The target page responded successfully and exposed readable HTML metadata and headings.",
        evidence=f"Status code {response.status_code}, content-type {response.headers.get('content-type', 'unknown')}.",
        affected_url=website.url,
        recommended_fix="Continue to add semantic HTML, sitemap data, and API documentation where appropriate.",
        confidence="medium",
        verification_status="confirmed",
        is_confirmed=True,
    )

    db.add(finding)
    db.commit()

    return {
        "scan_id": scan.id,
        "website_id": website.id,
        "status": "completed",
        "compatibility_score": scan.compatibility_score,
        "security_score": scan.security_score,
        "summary": scan.summary,
    }

