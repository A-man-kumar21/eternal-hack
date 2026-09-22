"""SQLAlchemy 2 models for e-Abhilekh."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    INVESTIGATOR = "INVESTIGATOR"
    LEGAL_REVIEWER = "LEGAL_REVIEWER"
    EVIDENCE_CUSTODIAN = "EVIDENCE_CUSTODIAN"
    SECURITY_AUDITOR = "SECURITY_AUDITOR"


class DocType(str, enum.Enum):
    FIR = "FIR"
    EVIDENCE_PHOTO = "EVIDENCE_PHOTO"
    CHARGE_SHEET = "CHARGE_SHEET"
    COURT_FILING = "COURT_FILING"
    STATEMENT = "STATEMENT"
    OTHER = "OTHER"


class DocStatus(str, enum.Enum):
    INGESTING = "INGESTING"
    QUARANTINED = "QUARANTINED"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    FROZEN = "FROZEN"
    EXPORTED = "EXPORTED"
    ARCHIVED = "ARCHIVED"


class CustodyAction(str, enum.Enum):
    handoff = "handoff"
    accept = "accept"
    release = "release"


class AuditOutcome(str, enum.Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    INCIDENT = "INCIDENT"


class RedactionStatus(str, enum.Enum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"


class ExportStatus(str, enum.Enum):
    building = "building"
    ready = "ready"
    failed = "failed"


class ScanStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class AVStatus(str, enum.Enum):
    pending = "pending"    # scan not run yet
    clean = "clean"        # scanned, no threats found
    positive = "positive"  # threat found (document is quarantined instead)
    skipped = "skipped"    # no AV service configured or unreachable


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[Role] = mapped_column(Enum(Role), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[list["CaseMember"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class CaseMember(Base):
    __tablename__ = "case_members"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role))  # member's role on this case
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped["Case"] = relationship(back_populates="members")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    doc_type: Mapped[DocType] = mapped_column(Enum(DocType))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[DocStatus] = mapped_column(Enum(DocStatus), default=DocStatus.INGESTING, index=True)
    current_version_id: Mapped[int | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True)
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    version_number: Mapped[int] = mapped_column()
    object_key: Mapped[str] = mapped_column(String(256), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column()
    mime_type: Mapped[str] = mapped_column(String(128))
    wrapped_dek: Mapped[str] = mapped_column(Text)  # hex
    dek_nonce: Mapped[str] = mapped_column(String(64))  # hex
    gcm_nonce: Mapped[str] = mapped_column(String(64))  # hex
    gcm_tag: Mapped[str] = mapped_column(String(64))  # hex
    is_derivative: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_version_id: Mapped[int | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True)
    redaction_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    av_status: Mapped[AVStatus] = mapped_column(Enum(AVStatus), default=AVStatus.pending)
    av_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustodyEvent(Base):
    __tablename__ = "custody_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    action: Mapped[CustodyAction] = mapped_column(Enum(CustodyAction))
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    object_type: Mapped[str] = mapped_column(String(64), default="")
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[AuditOutcome] = mapped_column(Enum(AuditOutcome), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))


class AuditAnchor(Base):
    """Append-only anchor of audit chain heads.

    Written ONLY by the anchor job (POST /audit/anchor). Nothing in the app
    ever updates or deletes rows here — it is the independent reference
    point verify-chain compares the live chain against, so an admin who
    rewrites history and reforges hashes in ``audit_events`` is still caught.

    For demo purposes this lives in the app DB; in production it would be a
    separate store/service with independent credentials.
    """

    __tablename__ = "audit_anchors"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    anchored_hash: Mapped[str] = mapped_column(String(64))
    events_anchored: Mapped[int] = mapped_column()  # chain length at anchor time
    anchored_by: Mapped[str] = mapped_column(String(64), default="anchor-job")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RedactionMark(Base):
    __tablename__ = "redaction_marks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id"), index=True)
    page: Mapped[int] = mapped_column()
    bbox: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)  # [x0,y0,x1,y1] or null
    label: Mapped[str] = mapped_column(String(32))  # AADHAAR|PHONE|EMAIL|NAME
    confidence: Mapped[float] = mapped_column()
    text_excerpt: Mapped[str] = mapped_column(Text)
    matched_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # exact regex hit (leak check)
    status: Mapped[RedactionStatus] = mapped_column(Enum(RedactionStatus), default=RedactionStatus.proposed)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ExportBundle(Base):
    __tablename__ = "export_bundles"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    status: Mapped[ExportStatus] = mapped_column(Enum(ExportStatus), default=ExportStatus.building)
    object_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # envelope-encryption params for the stored ZIP (same scheme as document blobs)
    wrapped_dek: Mapped[str | None] = mapped_column(Text, nullable=True)
    dek_nonce: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gcm_nonce: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gcm_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.pending, index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
