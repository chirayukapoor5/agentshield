from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool = True


class WebsiteCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    url: str = Field(..., min_length=5, max_length=500)


class WebsiteOut(BaseModel):
    id: int
    name: str
    url: str
    status: str
    owner_verified: bool
    created_at: datetime


class ScanOut(BaseModel):
    id: int
    website_id: int
    status: str
    compatibility_score: float
    security_score: float
    started_at: datetime
    finished_at: datetime | None = None
    summary: str | None = None


class FindingOut(BaseModel):
    id: int
    website_id: int
    severity: str
    title: str
    category: str
    description: str
    evidence: str | None = None
    affected_url: str | None = None
    recommended_fix: str | None = None
    confidence: str
    verification_status: str
    is_confirmed: bool


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    permissions: dict = Field(default_factory=dict)


class AgentOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool
    permissions: dict
    created_at: datetime


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    effect: str = "allow"
    decision_mode: str = "dry_run"
    rules: dict = Field(default_factory=dict)
    website_id: int | None = None


class PolicyOut(BaseModel):
    id: int
    name: str
    effect: str
    decision_mode: str
    rules: dict
    website_id: int | None = None


class AuditEventOut(BaseModel):
    id: int
    event_type: str
    resource_type: str
    resource_id: str | None = None
    request_id: str | None = None
    details: dict
    created_at: datetime

