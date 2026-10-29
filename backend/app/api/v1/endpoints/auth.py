from fastapi import APIRouter

from app.api.v1.endpoints import agents, audit, auth, policies, websites

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(websites.router, prefix="/websites", tags=["websites"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(policies.router, prefix="/policies", tags=["policies"])
api_router.include_router(audit.router, prefix="/audit-events", tags=["audit"])

