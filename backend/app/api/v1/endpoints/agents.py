from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, get_db
from app.models.models import Finding, Scan, Website
from app.schemas.website import WebsiteCreate, WebsiteOut
from app.services.scan_service import run_scan

router = APIRouter()


@router.get("", response_model=list[WebsiteOut])
def list_websites(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    websites = db.query(Website).filter(Website.organization_id == current_user.organization_id).all()
    return [WebsiteOut(**website.__dict__) for website in websites]


@router.post("", response_model=WebsiteOut, status_code=201)
def create_website(payload: WebsiteCreate, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    website = Website(
        organization_id=current_user.organization_id,
        name=payload.name,
        url=payload.url,
        status="registered",
        owner_verified=False,
    )
    db.add(website)
    db.commit()
    db.refresh(website)
    return WebsiteOut(**website.__dict__)


@router.get("/{website_id}", response_model=WebsiteOut)
def get_website(website_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return WebsiteOut(**website.__dict__)


@router.post("/{website_id}/verify", response_model=WebsiteOut)
def verify_website(website_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    website.owner_verified = True
    website.status = "verified"
    db.commit()
    db.refresh(website)
    return WebsiteOut(**website.__dict__)


@router.post("/{website_id}/scans")
def create_scan(website_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return run_scan(db, website)


@router.get("/{website_id}/findings")
def get_findings(website_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    findings = db.query(Finding).filter(Finding.website_id == website.id).all()
    return [{
        "id": item.id,
        "website_id": item.website_id,
        "title": item.title,
        "severity": item.severity,
        "category": item.category,
        "description": item.description,
        "evidence": item.evidence,
        "affected_url": item.affected_url,
        "recommended_fix": item.recommended_fix,
        "confidence": item.confidence,
        "verification_status": item.verification_status,
        "is_confirmed": item.is_confirmed,
    } for item in findings]


@router.get("/{website_id}/reports")
def get_reports(website_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return []
