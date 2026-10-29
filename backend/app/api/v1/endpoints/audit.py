from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, get_db
from app.models.models import AuditEvent, User
from app.schemas.audit import AuditEventOut

router = APIRouter()


@router.get("", response_model=list[AuditEventOut])
def list_audit_events(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    events = db.query(AuditEvent).filter(AuditEvent.organization_id == current_user.organization_id).order_by(AuditEvent.id.desc()).all()
    return [AuditEventOut(**event.__dict__) for event in events]
