"""AV scan status per document version.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    av_enum = sa.Enum("pending", "clean", "positive", "skipped", name="avstatus")
    av_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "document_versions",
        sa.Column("av_status", av_enum, nullable=False, server_default="pending"),
    )
    op.add_column("document_versions", sa.Column("av_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_versions", "av_detail")
    op.drop_column("document_versions", "av_status")
    sa.Enum(name="avstatus").drop(op.get_bind(), checkfirst=True)
