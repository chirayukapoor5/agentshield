from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Finding, Report, Website


def build_report_payload(db: Session, website_id: int) -> dict:
    website = db.query(Website).filter(Website.id == website_id).first()
    findings = db.query(Finding).filter(Finding.website_id == website_id).all()
    summary = {
        "website": website.name if website else "Unknown website",
        "url": website.url if website else "",
        "finding_count": len(findings),
        "highest_severity": max((item.severity for item in findings), default="none"),
    }
    return {
        "website_id": website_id,
        "format": "json",
        "summary": summary,
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
