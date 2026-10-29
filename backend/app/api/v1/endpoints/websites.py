from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_active_user, get_db
from app.models.models import Finding, Scan, User, Website
from app.schemas.website import (
    WebsiteCreated,
    WebsiteCreate,
    WebsiteOut,
    WebsiteVerificationOut,
)
from app.services.audit_service import record_audit_event
from app.services.verification_service import (
    issue_verification_token,
    normalize_website_url,
    verification_dns_name,
    verify_dns_token,
)

router = APIRouter()


def _website_for_user(db: Session, website_id: int, user: User) -> Website:
    website = (
        db.query(Website)
        .filter(
            Website.id == website_id,
            Website.organization_id == user.organization_id,
        )
        .first()
    )
    if website is None:
        raise HTTPException(status_code=404, detail="Website not found")
    return website


def _verification_instructions(website: Website, token: str, expires_at: datetime) -> WebsiteVerificationOut:
    dns_name = verification_dns_name(website.url)
    return WebsiteVerificationOut(
        website_id=website.id,
        verification_status=website.verification_status,
        verification_dns_name=dns_name,
        verification_token=token,
        expires_at=expires_at,
        instructions=(
            f"Create a DNS TXT record named {dns_name} with the exact value {token}. "
            f"Allow DNS time to propagate, then request verification before {expires_at.isoformat()} UTC."
        ),
    )


@router.get("", response_model=list[WebsiteOut])
def list_websites(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return (
        db.query(Website)
        .filter(Website.organization_id == current_user.organization_id)
        .order_by(Website.id.asc())
        .all()
    )


@router.post("", response_model=WebsiteCreated, status_code=status.HTTP_201_CREATED)
def create_website(
    payload: WebsiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    website = Website(
        organization_id=current_user.organization_id,
        name=payload.name,
        url=normalize_website_url(str(payload.url)),
        status="pending_verification",
        verification_status="pending",
        owner_verified=False,
        verification_attempts=0,
    )
    token, expires_at = issue_verification_token(website)
    db.add(website)
    db.flush()
    record_audit_event(db, current_user, "website.registered", "website", website.id, {
        "status": "pending_verification",
    })
    db.commit()
    db.refresh(website)
    instructions = _verification_instructions(website, token, expires_at)
    return WebsiteCreated(
        **WebsiteOut.model_validate(website).model_dump(),
        verification_token=token,
        verification_dns_name=instructions.verification_dns_name,
        verification_instructions=instructions.instructions,
    )


@router.post("/{website_id}/verification", response_model=WebsiteVerificationOut)
def renew_verification(
    website_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    website = _website_for_user(db, website_id, current_user)
    try:
        token, expires_at = issue_verification_token(website)
    except HTTPException as exc:
        record_audit_event(db, current_user, "website.verification_token_rejected", "website", website.id, {
            "reason": exc.status_code,
        })
        db.commit()
        raise
    record_audit_event(db, current_user, "website.verification_token_issued", "website", website.id, {
        "expires_at": expires_at.isoformat(),
    })
    db.commit()
    return _verification_instructions(website, token, expires_at)


@router.post("/{website_id}/verify", response_model=WebsiteOut)
def verify_website(
    website_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    website = _website_for_user(db, website_id, current_user)
    try:
        verified = verify_dns_token(website)
    except HTTPException as exc:
        record_audit_event(db, current_user, "website.verification_attempt", "website", website.id, {
            "result": "rejected",
            "reason": exc.status_code,
        })
        db.commit()
        raise

    record_audit_event(db, current_user, "website.verification_attempt", "website", website.id, {
        "result": "verified" if verified else "token_not_found",
        "attempt": website.verification_attempts,
    })
    db.commit()
    if not verified:
        if website.verification_attempts >= settings.VERIFICATION_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed verification attempts. Request a new token after the lockout.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"TXT record not found or token did not match at {verification_dns_name(website.url)}.",
        )
    db.refresh(website)
    return website


@router.get("/{website_id}", response_model=WebsiteOut)
def get_website(
    website_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return _website_for_user(db, website_id, current_user)


@router.post("/{website_id}/scans")
def create_scan(
    website_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    website = _website_for_user(db, website_id, current_user)
    if not website.owner_verified or website.verification_status != "verified":
        record_audit_event(db, current_user, "website.scan_rejected", "website", website.id, {
            "reason": "ownership_not_verified",
        })
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify website ownership before starting a scan.",
        )

    from app.services.scan_service import run_scan

    try:
        result = run_scan(db, website)
    except Exception:
        record_audit_event(db, current_user, "website.scan_failed", "website", website.id, {
            "reason": "internal_error",
        })
        db.commit()
        raise
    record_audit_event(
        db,
        current_user,
        "website.scan_completed" if result["status"] == "completed" else "website.scan_failed",
        "scan",
        result["id"],
        {"website_id": website.id, "status": result["status"]},
    )
    db.commit()
    return result


@router.get("/{website_id}/scans")
def get_scans(
    website_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    website = _website_for_user(db, website_id, current_user)
    scans = (
        db.query(Scan)
        .filter(Scan.website_id == website.id, Scan.scanner_version.isnot(None))
        .order_by(Scan.id.desc())
        .all()
    )
    return [
        {
            "id": scan.id,
            "status": scan.status,
            "scanner_version": scan.scanner_version,
            "compatibility_score": scan.compatibility_score,
            "security_score": scan.security_score,
            "score_coverage": (scan.check_results or {}).get("score_coverage", {}),
            "checks": (scan.check_results or {}).get("checks", []),
            "summary": scan.summary,
            "started_at": scan.started_at,
            "finished_at": scan.finished_at,
        }
        for scan in scans
    ]


@router.get("/{website_id}/findings")
def get_findings(
    website_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    website = _website_for_user(db, website_id, current_user)
    findings = (
        db.query(Finding)
        .filter(Finding.website_id == website.id, Finding.scan_id.isnot(None))
        .order_by(Finding.id.desc())
        .all()
    )
    return [
        {
            "id": item.id,
            "website_id": item.website_id,
            "scan_id": item.scan_id,
            "finding_type": item.finding_type,
            "title": item.title,
            "severity": item.severity,
            "category": item.category,
            "description": item.description,
            "evidence": item.evidence,
            "affected_url": item.affected_url,
            "recommended_fix": item.recommended_fix,
            "confidence": item.confidence,
            "verification_status": item.verification_status,
            "detected_at": item.detected_at,
            "scanner_version": item.scanner_version,
        }
        for item in findings
    ]


@router.get("/{website_id}/reports")
def get_reports(
    website_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    website = _website_for_user(db, website_id, current_user)
    scans = (
        db.query(Scan)
        .filter(Scan.website_id == website.id, Scan.scanner_version.isnot(None))
        .order_by(Scan.id.desc())
        .all()
    )
    return [
        {
            "id": scan.id,
            "status": scan.status,
            "scanner_version": scan.scanner_version,
            "compatibility_score": scan.compatibility_score,
            "security_score": scan.security_score,
            "check_results": scan.check_results,
            "summary": scan.summary,
            "started_at": scan.started_at,
            "finished_at": scan.finished_at,
        }
        for scan in scans
    ]
