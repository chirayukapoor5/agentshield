from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    user_id: int | None = None
    event_type: str
    resource_type: str
    resource_id: str | None = None
    request_id: str | None = None
    details: dict
    created_at: datetime
