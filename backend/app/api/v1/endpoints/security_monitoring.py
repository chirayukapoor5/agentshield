"""Authenticated organization-scoped telemetry API.

Intended for trusted human dashboard use with existing bearer auth.
Not an agent API-key ingestion service. Never accepts raw prompt/arguments.
"""
from datetime import datetime
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.models import User
from app.models.security_monitoring import SecurityIncident, SecurityTelemetry

router = APIRouter()
SAFE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")

class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    tool: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    reason: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    allowed: bool

class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str

@router.post("/events", status_code=201)
def ingest_event(payload: EventIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_active_user)):
    org = user.organization_id
    previous = db.query(SecurityTelemetry).filter_by(
        organization_id=org, event_id=payload.event_id).first()
    if previous:
        if (previous.tool, previous.reason, previous.allowed) != (
                payload.tool, payload.reason, payload.allowed):
            raise HTTPException(409, "event_id already used with different metadata")
        return {"id": previous.id, "duplicate": True}
    event = SecurityTelemetry(organization_id=org, **payload.model_dump())
    db.add(event)
    try:
        db.flush()
        if not payload.allowed:
            incident = db.query(SecurityIncident).filter_by(
                organization_id=org, tool=payload.tool).first()
            if incident is None:
                incident = SecurityIncident(organization_id=org, tool=payload.tool,
                                            denial_count=0)
                db.add(incident)
            incident.denial_count += 1
            incident.severity = "high" if incident.denial_count >= 3 else "medium"
            incident.updated_at = datetime.utcnow()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "concurrent event conflict; retry request")
    return {"id": event.id, "duplicate": False}

@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    org = user.organization_id
    events = db.query(SecurityTelemetry).filter_by(organization_id=org).order_by(
        SecurityTelemetry.id.desc()).limit(100).all()
    incidents = db.query(SecurityIncident).filter_by(organization_id=org).order_by(
        SecurityIncident.id.desc()).limit(100).all()
    return {
        "events": [{"id": e.id, "event_id": e.event_id, "tool": e.tool,
                    "reason": e.reason, "allowed": e.allowed,
                    "created_at": e.created_at.isoformat()} for e in events],
        "incidents": [{"id": i.id, "tool": i.tool, "denial_count": i.denial_count,
                       "severity": i.severity, "status": i.status,
                       "updated_at": i.updated_at.isoformat()} for i in incidents],
        "scope": "authenticated_organization", "limit_per_collection": 100,
    }

@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: int, payload: StatusIn,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_active_user)):
    if payload.status not in {"open", "investigating", "resolved"}:
        raise HTTPException(422, "invalid incident status")
    incident = db.query(SecurityIncident).filter_by(
        id=incident_id, organization_id=user.organization_id).first()
    if incident is None:
        raise HTTPException(404, "incident not found")
    if incident.status == "resolved" and payload.status == "investigating":
        raise HTTPException(409, "reopen incident before investigating")
    incident.status = payload.status
    incident.updated_at = datetime.utcnow()
    db.commit()
    return {"id": incident.id, "status": incident.status}
