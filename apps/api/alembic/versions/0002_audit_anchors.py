"""Audit chain anchors (append-only).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_anchors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("anchored_hash", sa.String(64), nullable=False),
        sa.Column("events_anchored", sa.Integer(), nullable=False),
        sa.Column("anchored_by", sa.String(64), nullable=False, server_default="anchor-job"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_audit_anchors_case_id", "audit_anchors", ["case_id"])
    op.create_index("ix_audit_anchors_created_at", "audit_anchors", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_anchors_created_at", table_name="audit_anchors")
    op.drop_index("ix_audit_anchors_case_id", table_name="audit_anchors")
    op.drop_table("audit_anchors")
