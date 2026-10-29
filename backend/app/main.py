from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.models import Organization, User

from app.api.v1.api import api_router


def create_demo_data() -> None:
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.slug == "demo-org").first()
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


Base.metadata.create_all(bind=engine)
create_demo_data()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="AgentShield API for AI-agent compatibility and security assessment.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"app": settings.APP_NAME, "status": "ok"}
