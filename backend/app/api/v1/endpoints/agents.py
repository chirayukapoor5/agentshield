from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, get_db
from app.models.models import Organization, Scan, User, Website
from app.schemas.website import WebsiteCreate, WebsiteOut
from app.services.scan_service import run_scan

router = APIRouter()


@router.get("", response_model=list[WebsiteOut])
def list_websites(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org_id = current_user.organization_id
    websites = db.query(Website).filter(Website.organization_id == org_id).all()
    return [WebsiteOut(**w.__dict__) for w in websites]


@router.post("", response_model=WebsiteOut, status_code=status.HTTP_201_CREATED)
def create_website(payload: WebsiteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
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
def get_website(website_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return WebsiteOut(**website.__dict__)


@router.post("/{website_id}/verify", response_model=WebsiteOut)
def verify_website(website_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    website.owner_verified = True
    website.status = "verified"
    db.commit()
    db.refresh(website)
    return WebsiteOut(**website.__dict__)


@router.post("/{website_id}/scans", response_model=dict)
def create_scan(website_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    result = run_scan(db, website)
    return result


@router.get("/{website_id}/findings", response_model=list[dict])
def get_findings(website_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    findings = db.query(Website).filter(Website.id == website_id).first()
    return []


@router.get("/{website_id}/reports", response_model=list[dict])
def get_reports(website_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    website = db.query(Website).filter(Website.id == website_id, Website.organization_id == current_user.organization_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return []

