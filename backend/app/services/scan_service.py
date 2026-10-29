from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Finding, Scan, Website
from app.services.safe_scanner import SCANNER_VERSION, ScanRequestError, run_safe_scan


def run_scan(db: Session, website: Website) -> dict:
    if not website.owner_verified or website.verification_status != "verified":
        raise ValueError("Website ownership must be verified before scanning.")

    scan = Scan(
        website_id=website.id,
        status="running",
        compatibility_score=None,
        security_score=None,
        scanner_version=SCANNER_VERSION,
        check_results=[],
        started_at=datetime.utcnow(),
        summary="Safe, non-destructive website checks are running.",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    try:
        result = run_safe_scan(website.url)
    except ScanRequestError as exc:
        scan.status = "failed"
        scan.summary = str(exc)
        scan.check_results = {
            "checks": [{
                "id": "scan",
                "label": "Scan execution",
                "status": "unavailable",
                "reason": exc.kind,
                "evidence": str(exc),
            }],
            "score_coverage": {},
        }
        scan.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(scan)
        return _scan_payload(scan)
    except Exception:
        scan.status = "failed"
        scan.summary = "An internal scanner error interrupted the scan. See server logs."
        scan.check_results = {
            "checks": [{
                "id": "scan",
                "label": "Scan execution",
                "status": "unavailable",
                "reason": "internal_error",
                "evidence": "The scanner raised an unexpected error; details were not exposed in the API response.",
            }],
            "score_coverage": {},
        }
        scan.finished_at = datetime.utcnow()
        db.commit()
        raise

    detected_at = datetime.utcnow()
    scan.status = (
        "completed"
        if any(check["status"] != "unavailable" for check in result["checks"])
        else "failed"
    )
    scan.compatibility_score = result["compatibility_score"]
    scan.security_score = result["security_score"]
    scan.check_results = {
        "checks": result["checks"],
        "score_coverage": result["score_coverage"],
    }
    scan.summary = result["summary"]
    scan.finished_at = datetime.utcnow()

    for item in result["findings"]:
        db.add(Finding(
            website_id=website.id,
            scan_id=scan.id,
            finding_type=item["finding_type"],
            severity=item["severity"],
            title=item["title"],
            category=item["finding_type"],
            description=item["title"],
            evidence=item["evidence"],
            affected_url=item["affected_url"],
            recommended_fix=item["recommended_fix"],
            confidence=item["confidence"],
            verification_status=item["verification_status"],
            is_confirmed=item["verification_status"] == "confirmed",
            detected_at=detected_at,
            scanner_version=SCANNER_VERSION,
        ))
    db.commit()
    db.refresh(scan)
    return _scan_payload(scan)


def _scan_payload(scan: Scan) -> dict:
    check_results = scan.check_results or {}
    checks = check_results.get("checks", [])
    score_coverage = check_results.get("score_coverage", {})
    return {
        "id": scan.id,
        "website_id": scan.website_id,
        "status": scan.status,
        "scanner_version": scan.scanner_version,
        "compatibility_score": scan.compatibility_score,
        "security_score": scan.security_score,
        "score_coverage": score_coverage,
        "checks": checks,
        "summary": scan.summary,
        "started_at": scan.started_at,
        "finished_at": scan.finished_at,
    }
