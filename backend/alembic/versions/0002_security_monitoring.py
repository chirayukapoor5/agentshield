"""Create tenant-scoped security monitoring tables.

Revision ID: 0002_security_monitoring
Revises: 0001_ownership_evidence
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_security_monitoring"
down_revision = "0001_ownership_evidence"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "security_telemetry" not in tables:
        op.create_table(
            "security_telemetry",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("event_id", sa.String(64), nullable=False),
            sa.Column("tool", sa.String(64), nullable=False),
            sa.Column("reason", sa.String(64), nullable=False),
            sa.Column("allowed", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("organization_id", "event_id", name="uq_org_security_event"),
        )
    if "security_incidents" not in tables:
        op.create_table(
            "security_incidents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("tool", sa.String(64), nullable=False),
            sa.Column("denial_count", sa.Integer(), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("organization_id", "tool", name="uq_org_incident_tool"),
        )
    inspector = inspect(bind)
    for table in ("security_telemetry", "security_incidents"):
        indexes = {idx["name"] for idx in inspector.get_indexes(table)}
        name = "ix_" + table + "_organization_id"
        if name not in indexes:
            op.create_index(name, table, ["organization_id"])

def downgrade():
    raise RuntimeError("Security telemetry migration is intentionally irreversible to prevent incident evidence loss.")
