from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: int
    organization_id: int
    user_id: int | None = None
    event_type: str
    resource_type: str
    resource_id: str | None = None
    request_id: str | None = None
    details: dict
    created_at: datetime
