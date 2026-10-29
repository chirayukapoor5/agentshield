from sqlalchemy import text

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
                password_hash="$2b$12$LZQ8i5fTZ1RzAu2Hq9O6K.6I4kG0s9t8B5sJbC0wVj7vQx6mC2pS",  # password: password123
                is_active=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()

