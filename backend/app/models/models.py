from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(120), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="organization")
    websites = relationship("Website", back_populates="organization")
    policies = relationship("Policy", back_populates="organization")
    agent_credentials = relationship("AgentCredential", back_populates="organization")
    audit_events = relationship("AuditEvent", back_populates="organization")
    reports = relationship("Report", back_populates="organization")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="users")
    websites = relationship("Website", back_populates="owner")
    audit_events = relationship("AuditEvent", back_populates="user")


class Website(Base):
    __tablename__ = "websites"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    status = Column(String(50), default="registered", nullable=False)
    owner_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="websites")
    owner = relationship("User", back_populates="websites")
    scans = relationship("Scan", back_populates="website")
    findings = relationship("Finding", back_populates="website")
    policies = relationship("Policy", back_populates="website")
    reports = relationship("Report", back_populates="website")


class Scan(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    status = Column(String(50), default="completed", nullable=False)
    compatibility_score = Column(Float, default=0.0, nullable=False)
    security_score = Column(Float, default=0.0, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)

    website = relationship("Website", back_populates="scans")


class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    severity = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    affected_url = Column(String(500), nullable=True)
    recommended_fix = Column(Text, nullable=True)
    confidence = Column(String(50), default="medium", nullable=False)
    verification_status = Column(String(50), default="pending", nullable=False)
    is_confirmed = Column(Boolean, default=False, nullable=False)

    website = relationship("Website", back_populates="findings")


class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    api_key_hash = Column(String(255), nullable=False)
    permissions = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    credentials = relationship("AgentCredential", back_populates="agent")


class AgentCredential(Base):
    __tablename__ = "agent_credentials"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    credential_name = Column(String(255), nullable=False)
    token = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="agent_credentials")
    agent = relationship("Agent", back_populates="credentials")


class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=True)
    name = Column(String(255), nullable=False)
    effect = Column(String(50), default="allow", nullable=False)
    decision_mode = Column(String(50), default="dry_run", nullable=False)
    rules = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="policies")
    website = relationship("Website", back_populates="policies")
    decisions = relationship("PolicyDecision", back_populates="policy")


class PolicyDecision(Base):
    __tablename__ = "policy_decisions"
    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    decision = Column(String(50), nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    policy = relationship("Policy", back_populates="decisions")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(String(120), nullable=False)
    resource_type = Column(String(120), nullable=False)
    resource_id = Column(String(255), nullable=True)
    request_id = Column(String(255), nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="audit_events")
    user = relationship("User", back_populates="audit_events")


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    format = Column(String(40), default="json", nullable=False)
    file_name = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="reports")
    website = relationship("Website", back_populates="reports")
