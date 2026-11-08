"""Organization-scoped security events and incident records."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from app.db.session import Base

class SecurityTelemetry(Base):
    __tablename__ = "security_telemetry"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    event_id = Column(String(64), nullable=False)
    tool = Column(String(64), nullable=False)
    reason = Column(String(64), nullable=False)
    allowed = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "event_id", name="uq_org_security_event"),)

class SecurityIncident(Base):
    __tablename__ = "security_incidents"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    tool = Column(String(64), nullable=False)
    denial_count = Column(Integer, nullable=False, default=0)
    severity = Column(String(16), nullable=False, default="medium")
    status = Column(String(16), nullable=False, default="open")
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "tool", name="uq_org_incident_tool"),)
