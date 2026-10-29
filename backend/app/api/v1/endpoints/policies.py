from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, get_db
from app.models.models import Policy, User, Website
from app.schemas.policy import PolicyCreate, PolicyOut
from app.services.audit_service import record_audit_event

router = APIRouter()


@router.get("", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    policies = db.query(Policy).filter(Policy.organization_id == current_user.organization_id).all()
    return [PolicyOut(**policy.__dict__) for policy in policies]


@router.post("", response_model=PolicyOut, status_code=201)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.website_id is not None:
        website = (
            db.query(Website)
            .filter(
                Website.id == payload.website_id,
                Website.organization_id == current_user.organization_id,
            )
            .first()
        )
        if website is None:
            raise HTTPException(status_code=404, detail="Website not found")
    policy = Policy(
        organization_id=current_user.organization_id,
        website_id=payload.website_id,
        name=payload.name,
        effect=payload.effect,
        decision_mode=payload.decision_mode,
        rules=payload.rules,
    )
    db.add(policy)
    db.flush()
    record_audit_event(db, current_user, "policy.created", "policy", policy.id, {
        "website_id": policy.website_id,
        "decision_mode": policy.decision_mode,
    })
    db.commit()
    db.refresh(policy)
    return PolicyOut(**policy.__dict__)
