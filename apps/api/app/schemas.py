"""Pydantic v2 request/response schemas (API surface per CONTRACT.md)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------- auth ----------
class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# ---------- cases ----------
class CaseCreateIn(BaseModel):
    case_number: str
    title: str
    description: str = ""


class CaseMemberIn(BaseModel):
    user_id: int
    role: Literal["INVESTIGATOR", "LEGAL_REVIEWER", "EVIDENCE_CUSTODIAN", "SECURITY_AUDITOR"]


class MemberOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: str


class CaseOut(BaseModel):
    id: int
    case_number: str
    title: str
    description: str
    status: str
    created_by: int
    created_at: str
    members: list[MemberOut]
    document_count: int


class CaseSummaryOut(BaseModel):
    id: int
    case_number: str
    title: str
    description: str
    status: str
    created_by: int
    created_at: str


# ---------- documents ----------
class DocumentCreateForm(BaseModel):
    title: str
    doc_type: Literal["FIR", "EVIDENCE_PHOTO", "CHARGE_SHEET", "COURT_FILING", "STATEMENT", "OTHER"]
    description: str = ""
    reason: str = ""


class UploadAcceptedOut(BaseModel):
    document_id: int
    version_id: int | None = None
    status: str


class VersionOut(BaseModel):
    id: int
    document_id: int
    version_number: int
    sha256: str
    size_bytes: int
    mime_type: str
    is_derivative: bool
    parent_version_id: int | None
    redaction_summary: dict | None
    av_status: str = "pending"
    av_detail: str | None = None
    created_by: int
    created_at: str


class CurrentVersionOut(BaseModel):
    id: int
    version_number: int
    sha256: str
    size_bytes: int
    mime_type: str
    av_status: str = "pending"
    av_detail: str | None = None
    created_at: str
    created_by: int


class DocumentOut(BaseModel):
    id: int
    case_id: int
    title: str
    doc_type: str
    description: str
    status: str
    current_version: CurrentVersionOut | None
    version_count: int
    created_at: str
    quarantine_reason: str | None = None


class VerifyOut(BaseModel):
    document_id: int
    version_id: int
    stored_sha256: str
    computed_sha256: str
    match: bool
    verified_at: str


class FreezeIn(BaseModel):
    reason: str


# ---------- custody ----------
class CustodyIn(BaseModel):
    action: Literal["handoff", "accept", "release"]
    to_user_id: int | None = None
    reason: str = ""


class CustodyOut(BaseModel):
    id: int
    document_id: int
    action: str
    from_user_id: int
    to_user_id: int | None
    reason: str
    created_at: str


# ---------- redaction ----------
class RedactionMarkOut(BaseModel):
    mark_id: int
    page: int
    bbox: list | dict | None
    label: str
    confidence: float
    text_excerpt: str


class AnalyzeOut(BaseModel):
    version_id: int
    marks: list[RedactionMarkOut]
    note: str | None = None


class ApprovalIn(BaseModel):
    mark_id: int
    approved: bool


class RedactIn(BaseModel):
    approvals: list[ApprovalIn]
    reason: str = ""


class RedactOut(BaseModel):
    derivative_version_id: int
    version_number: int
    sha256: str


# ---------- export ----------
class ExportIn(BaseModel):
    document_ids: list[int]
    reason: str = ""


class ExportAcceptedOut(BaseModel):
    bundle_id: int
    status: str


class ExportOut(BaseModel):
    id: int
    case_id: int
    status: str
    sha256: str | None
    created_at: str
    created_by: int
    manifest: dict | None


# ---------- audit / alerts ----------
class AuditEventOut(BaseModel):
    id: int
    case_id: int | None
    case_number: str | None = None
    actor_id: int | None
    actor_name: str | None
    action: str
    object_type: str
    object_id: str | None
    outcome: str
    reason: str | None
    request_id: str
    created_at: str
    event_hash: str
    prev_hash: str


class VerifyChainOut(BaseModel):
    ok: bool
    events_checked: int
    broken_at_id: int | None
    last_anchored_hash: str | None = None
    anchor_diverged: bool = False


class AnchorOut(BaseModel):
    case_id: int
    anchored_hash: str
    events_anchored: int
    anchored_at: str


class TimelineEventOut(BaseModel):
    id: str
    kind: str
    actor: str | None
    action: str
    object_id: str | None
    reason: str | None
    created_at: str
    detail: dict[str, Any] = Field(default_factory=dict)


class TimelineOut(BaseModel):
    events: list[TimelineEventOut]


class AlertsOut(BaseModel):
    alerts: list[AuditEventOut]


# ---------- error envelope ----------
class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
