from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_active_user, get_db, hash_password, verify_password
from app.models.models import Organization, User
from app.schemas.website import Token, UserOut, UserRegister
from app.services.audit_service import record_audit_event

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    organization = Organization(
        name=f"{payload.full_name}'s organization",
        slug=f"org-{uuid4().hex}",
    )
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=str(payload.email),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    record_audit_event(db, user, "user.registered", "organization", organization.id)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=Token)
def login_user(payload: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.email)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    return UserOut(**current_user.__dict__)
