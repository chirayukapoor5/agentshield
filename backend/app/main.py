from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.init_db import create_demo_data
from app.db.session import engine
from app.models.models import Base

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

Base.metadata.create_all(bind=engine)
create_demo_data()

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/")
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "docs": "/docs",
        "status": "operational",
    }

