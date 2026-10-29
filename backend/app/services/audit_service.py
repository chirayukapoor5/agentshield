from sqlalchemy.orm import Session

from app.models.models import AuditEvent, User


def record_audit_event(
    db: Session,
    user: User,
    event_type: str,
    resource_type: str,
    resource_id: int | str,
    details: dict | None = None,
) -> None:
    db.add(AuditEvent(
        organization_id=user.organization_id,
        user_id=user.id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id),
        details=details or {},
    ))
