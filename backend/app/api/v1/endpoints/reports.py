from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, get_db
from app.models.models import Report, User, Website

router = APIRouter()


@router.get("", response_model=list[dict])
def list_reports(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    reports = (
        db.query(Report)
        .join(Website, Report.website_id == Website.id)
        .filter(Website.organization_id == current_user.organization_id)
        .order_by(Report.id.desc())
        .all()
    )
    return [{
        "id": report.id,
        "website_id": report.website_id,
        "format": report.format,
        "file_name": report.file_name,
        "summary": report.summary,
        "created_at": report.created_at,
    } for report in reports]


@router.post("/{website_id}", response_model=dict)
def generate_report(website_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from app.services.report_service import build_report_payload, save_report
    payload = build_report_payload(db, website_id)
    saved = save_report(db, website_id, payload)
    return {"report_id": saved.id, **payload}
