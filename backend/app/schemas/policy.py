from datetime import datetime

from pydantic import BaseModel, Field


class WebsiteCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    url: str = Field(..., min_length=5, max_length=500)


class WebsiteOut(BaseModel):
    id: int
    organization_id: int
    name: str
    url: str
    status: str
    owner_verified: bool
    created_at: datetime

