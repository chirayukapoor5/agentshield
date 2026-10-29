from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Finding, Report, Scan, Website


def build_report_payload(db: Session, website_id: int) -> dict:
    website = db.query(Website).filter(Website.id == website_id).first()
    findings = (
        db.query(Finding)
        .filter(Finding.website_id == website_id, Finding.scan_id.isnot(None))
        .order_by(Finding.id.asc())
        .all()
    )
    latest_scan = (
        db.query(Scan)
        .filter(Scan.website_id == website_id, Scan.scanner_version.isnot(None))
        .order_by(Scan.id.desc())
        .first()
    )
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    highest_severity = max(
        (item.severity for item in findings),
        key=lambda value: severity_rank.get(value.lower(), 0),
        default="none",
    )
    summary = {
        "website": website.name if website else "Unknown website",
        "url": website.url if website else "",
        "finding_count": len(findings),
        "highest_severity": highest_severity,
        "scan_status": latest_scan.status if latest_scan else "not_scanned",
        "scan_summary": latest_scan.summary if latest_scan else None,
    }
    return {
        "website_id": website_id,
        "format": "json",
        "summary": summary,
        "scanner_version": latest_scan.scanner_version if latest_scan else None,
        "checks": (latest_scan.check_results or {}).get("checks", []) if latest_scan else [],
        "findings": [
            {
                "type": item.finding_type,
                "title": item.title,
                "severity": item.severity,
                "affected_url": item.affected_url,
                "evidence": item.evidence,
                "confidence": item.confidence,
                "verification_status": item.verification_status,
                "detected_at": item.detected_at.isoformat() if item.detected_at else None,
                "recommended_fix": item.recommended_fix,
            }
            for item in findings
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }


def save_report(db: Session, website_id: int, payload: dict) -> Report:
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise ValueError("Website not found")

    report = Report(
        organization_id=website.organization_id,
        website_id=website_id,
        format=payload.get("format", "json"),
        file_name=f"report-{website_id}.json",
        summary=str(payload.get("summary", {})),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
