"""Initial schema for e-Abhilekh.

Revision ID: 0001
Revises:
Create Date: 2026-09-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("role", sa.Enum("INVESTIGATOR", "LEGAL_REVIEWER", "EVIDENCE_CUSTODIAN",
                                  "SECURITY_AUDITOR", name="role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_number", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_cases_case_number", "cases", ["case_number"])

    op.create_table(
        "case_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Enum("INVESTIGATOR", "LEGAL_REVIEWER", "EVIDENCE_CUSTODIAN",
                                  "SECURITY_AUDITOR", name="role"), nullable=False),
        sa.Column("added_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_member"),
    )
    op.create_index("ix_case_members_case_id", "case_members", ["case_id"])
    op.create_index("ix_case_members_user_id", "case_members", ["user_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("doc_type", sa.Enum("FIR", "EVIDENCE_PHOTO", "CHARGE_SHEET", "COURT_FILING",
                                      "STATEMENT", "OTHER", name="doctype"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Enum("INGESTING", "QUARANTINED", "ACTIVE", "UNDER_REVIEW",
                                    "FROZEN", "EXPORTED", "ARCHIVED", name="docstatus"),
                  nullable=False, server_default="INGESTING"),
        sa.Column("current_version_id", sa.Integer(), nullable=True),  # app-managed; no DB FK (cycle)
        sa.Column("quarantine_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(256), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("wrapped_dek", sa.Text(), nullable=False),
        sa.Column("dek_nonce", sa.String(64), nullable=False),
        sa.Column("gcm_nonce", sa.String(64), nullable=False),
        sa.Column("gcm_tag", sa.String(64), nullable=False),
        sa.Column("is_derivative", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parent_version_id", sa.Integer(),
                  sa.ForeignKey("document_versions.id"), nullable=True),
        sa.Column("redaction_summary", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

    op.create_table(
        "custody_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("action", sa.Enum("handoff", "accept", "release", name="custodyaction"),
                  nullable=False),
        sa.Column("from_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_custody_events_document_id", "custody_events", ["document_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("object_id", sa.String(64), nullable=True),
        sa.Column("outcome", sa.Enum("ALLOWED", "DENIED", "FAILED", "INCIDENT", name="auditoutcome"),
                  nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_outcome", "audit_events", ["outcome"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "redaction_marks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_version_id", sa.Integer(),
                  sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("text_excerpt", sa.Text(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("proposed", "approved", "rejected", name="redactionstatus"),
                  nullable=False, server_default="proposed"),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_redaction_marks_version", "redaction_marks", ["document_version_id"])

    op.create_table(
        "export_bundles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("status", sa.Enum("building", "ready", "failed", name="exportstatus"),
                  nullable=False, server_default="building"),
        sa.Column("object_key", sa.String(256), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("wrapped_dek", sa.Text(), nullable=True),
        sa.Column("dek_nonce", sa.String(64), nullable=True),
        sa.Column("gcm_nonce", sa.String(64), nullable=True),
        sa.Column("gcm_tag", sa.String(64), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_export_bundles_case_id", "export_bundles", ["case_id"])

    op.create_table(
        "scan_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "done", "failed", name="scanstatus"),
                  nullable=False, server_default="pending"),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_scan_jobs_document_id", "scan_jobs", ["document_id"])
    op.create_index("ix_scan_jobs_status", "scan_jobs", ["status"])


def downgrade() -> None:
    for t in ("scan_jobs", "export_bundles", "redaction_marks", "audit_events",
              "custody_events", "document_versions", "documents", "case_members",
              "cases", "refresh_tokens", "users"):
        op.drop_table(t)
    for e in ("role", "doctype", "docstatus", "custodyaction", "auditoutcome",
              "redactionstatus", "exportstatus", "scanstatus"):
        sa.Enum(name=e).drop(op.get_bind(), checkfirst=True)
