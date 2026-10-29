from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.models import Organization, User


def create_demo_data() -> None:
    db = SessionLocal()
    try:
        org = db.query(Organization).first()
        if org is None:
            org = Organization(name="Demo Org", slug="demo-org")
            db.add(org)
            db.commit()
            db.refresh(org)

        user = db.query(User).filter(User.email == "demo@agentshield.local").first()
        if user is None:
            user = User(
                organization_id=org.id,
                email="demo@agentshield.local",
                full_name="Demo Admin",
                password_hash=hash_password("password123"),
                is_active=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()
