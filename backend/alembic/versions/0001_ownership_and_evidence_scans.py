"""Bootstrap the existing prototype schema and add ownership/evidence fields.

This migration supports both new installations and databases created before Alembic
was configured. Subsequent schema changes should use normal immutable revisions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app.db.session import Base
from app.models import models  # noqa: F401

revision = "0001_ownership_evidence"
down_revision = None
branch_labels = None
depends_on = None


def _add_missing_columns(table: str, columns: dict[str, sa.Column]) -> None:
    inspector = inspect(op.get_bind())
    present = {column["name"] for column in inspector.get_columns(table)}
    missing = [column for name, column in columns.items() if name not in present]
    if missing:
        with op.batch_alter_table(table) as batch:
            for column in missing:
                batch.add_column(column)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    _add_missing_columns("websites", {
        "verification_token_hash": sa.Column("verification_token_hash", sa.String(length=64), nullable=True),
        "verification_expires_at": sa.Column("verification_expires_at", sa.DateTime(), nullable=True),
        "verification_status": sa.Column(
            "verification_status", sa.String(length=30), nullable=False, server_default="pending"
        ),
        "verification_attempts": sa.Column(
            "verification_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
        "verification_locked_until": sa.Column("verification_locked_until", sa.DateTime(), nullable=True),
        "verified_at": sa.Column("verified_at", sa.DateTime(), nullable=True),
    })
    _add_missing_columns("scans", {
        "scanner_version": sa.Column("scanner_version", sa.String(length=40), nullable=True),
        "check_results": sa.Column("check_results", sa.JSON(), nullable=True),
    })
    _add_missing_columns("findings", {
        "scan_id": sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scans.id"), nullable=True),
        "finding_type": sa.Column("finding_type", sa.String(length=120), nullable=True),
        "detected_at": sa.Column("detected_at", sa.DateTime(), nullable=True),
        "scanner_version": sa.Column("scanner_version", sa.String(length=40), nullable=True),
    })

    op.execute(
        "UPDATE websites SET owner_verified = FALSE, verification_status = 'pending', "
        "status = 'pending_verification', verified_at = NULL, verification_token_hash = NULL, "
        "verification_expires_at = NULL"
    )

    inspector = inspect(op.get_bind())
    scan_columns = {column["name"]: column for column in inspector.get_columns("scans")}
    if not scan_columns["compatibility_score"]["nullable"] or not scan_columns["security_score"]["nullable"]:
        with op.batch_alter_table("scans") as batch:
            if not scan_columns["compatibility_score"]["nullable"]:
                batch.alter_column(
                    "compatibility_score",
                    existing_type=sa.Float(),
                    nullable=True,
                )
            if not scan_columns["security_score"]["nullable"]:
                batch.alter_column(
                    "security_score",
                    existing_type=sa.Float(),
                    nullable=True,
                )

    inspector = inspect(op.get_bind())
    finding_indexes = {index["name"] for index in inspector.get_indexes("findings")}
    if "ix_findings_scan_id" not in finding_indexes:
        op.create_index("ix_findings_scan_id", "findings", ["scan_id"])


def downgrade() -> None:
    raise RuntimeError(
        "This bootstrap migration is intentionally irreversible to avoid deleting prototype data."
    )
