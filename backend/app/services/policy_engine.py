from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Finding, Report, Scan, Website


def build_report_payload(db: Session, website_id: int) -> dict:
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise ValueError("Website not found")

    scans = db.query(Scan).filter(Scan.website_id == website_id).order_by(Scan.id.desc()).all()
    findings = db.query(Finding).filter(Finding.website_id == website_id).all()

    compatibility_score = round(sum(scan.compatibility_score for scan in scans) / len(scans), 2) if scans else 0.0
    security_score = round(sum(scan.security_score for scan in scans) / len(scans), 2) if scans else 0.0

    sev_counter = Counter(item.severity for item in findings)
    report = {
        "website_id": website_id,
        "website_name": website.name,
        "url": website.url,
        "compatibility_score": compatibility_score,
        "security_score": security_score,
        "severity_distribution": dict(sorted(sev_counter.items())),
        "findings": [{
            "id": item.id,
            "severity": item.severity,
            "title": item.title,
            "description": item.description,
            "evidence": item.evidence,
            "recommended_fix": item.recommended_fix,
            "verification_status": item.verification_status,
            "confidence": item.confidence,
        } for item in findings],
        "generated_at": datetime.utcnow().isoformat(),
        "scan_count": len(scans),
        "scan_limitations": [
            "Passive checks are probabilistic and not a guarantee of total security coverage.",
            "External scans are limited to public and authorized endpoints.",
        ],
    }
    return report


def save_report(db: Session, website_id: int, payload: dict) -> Report:
    report = Report(
        website_id=website_id,
        scan_id=None,
        format="json",
        file_name=f"agentshield-report-{website_id}.json",
        summary=f"Compatibility score {payload['compatibility_score']}; security score {payload['security_score']}",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
