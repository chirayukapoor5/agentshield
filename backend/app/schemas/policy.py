from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    effect: str = "allow"
    decision_mode: str = "dry_run"
    rules: dict = Field(default_factory=dict)
    website_id: int | None = None


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    website_id: int | None = None
    name: str
    effect: str
    decision_mode: str
    rules: dict
    created_at: datetime
