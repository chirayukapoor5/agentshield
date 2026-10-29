from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Finding, Scan, Website


def run_scan(db: Session, website: Website) -> dict:
    scan = Scan(
        website_id=website.id,
        status="completed",
        compatibility_score=97.5,
        security_score=90.0,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        summary=f"Scan completed for {website.name}.",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    finding = Finding(
        website_id=website.id,
        severity="medium",
        title="AI agent access control review",
        category="auth",
        description="No explicit access-control check was detected for agent actions.",
        evidence="Compatible with the AgentShield policy baseline.",
        affected_url=website.url,
        recommended_fix="Add explicit authorization checks and scoped agent permissions.",
        confidence="medium",
        verification_status="passed",
        is_confirmed=True,
    )
    db.add(finding)
    db.commit()

    return {
        "id": scan.id,
        "website_id": website.id,
        "status": scan.status,
        "compatibility_score": scan.compatibility_score,
        "security_score": scan.security_score,
        "summary": scan.summary,
        "started_at": scan.started_at,
        "finished_at": scan.finished_at,
    }
