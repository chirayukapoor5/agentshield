from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, get_db
from app.models.models import Policy, User
from app.schemas.policy import PolicyCreate, PolicyOut

router = APIRouter()


@router.get("", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    policies = db.query(Policy).filter(Policy.organization_id == current_user.organization_id).all()
    return [PolicyOut(**policy.__dict__) for policy in policies]


@router.post("", response_model=PolicyOut, status_code=201)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    policy = Policy(
        organization_id=current_user.organization_id,
        website_id=payload.website_id,
        name=payload.name,
        effect=payload.effect,
        decision_mode=payload.decision_mode,
        rules=payload.rules,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyOut(**policy.__dict__)
