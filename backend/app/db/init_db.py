from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.models import Organization, User


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        organization = db.query(Organization).filter(Organization.slug == "demo-org").first()
        if organization is None:
            organization = Organization(name="Demo Org", slug="demo-org")
            db.add(organization)
            db.flush()

        user = db.query(User).filter(User.email == "demo@agentshield.local").first()
        if user is None:
            db.add(User(
                organization_id=organization.id,
                email="demo@agentshield.local",
                full_name="Demo Admin",
                password_hash=hash_password("password123"),
                is_active=True,
            ))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    initialize_database()
