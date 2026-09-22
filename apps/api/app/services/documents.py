"""Document read/download/verify/freeze service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import crypto
from ..audit import write_audit
from ..errors import BadRequest, NotFound
from ..models import (
    AuditOutcome,
    Document,
    DocumentVersion,
    DocStatus,
    User,
)
from ..storage import BaseStorage, get_storage
from .policy import require_case_access
from .redaction import _decrypt_version


def _doc_or_404(db: Session, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document not found")
    return doc


def _current_version(db: Session, doc: Document) -> DocumentVersion | None:
    return db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None


def document_to_dict(db: Session, doc: Document) -> dict:
    v = _current_version(db, doc)
    version_count = db.execute(
        select(func.count()).select_from(DocumentVersion).where(DocumentVersion.document_id == doc.id)
    ).scalar() or 0
    out = {
        "id": doc.id, "case_id": doc.case_id, "title": doc.title,
        "doc_type": doc.doc_type.value, "description": doc.description,
        "status": doc.status.value,
        "current_version": (
            {
                "id": v.id, "version_number": v.version_number, "sha256": v.sha256,
                "size_bytes": v.size_bytes, "mime_type": v.mime_type,
                "created_at": v.created_at.isoformat(), "created_by": v.created_by,
            } if v else None
        ),
        "version_count": version_count, "created_at": doc.created_at.isoformat(),
    }
    if doc.status == DocStatus.QUARANTINED:
        out["quarantine_reason"] = doc.quarantine_reason
    return out


def version_to_dict(v: DocumentVersion) -> dict:
    return {
        "id": v.id, "document_id": v.document_id, "version_number": v.version_number,
        "sha256": v.sha256, "size_bytes": v.size_bytes, "mime_type": v.mime_type,
        "is_derivative": v.is_derivative, "parent_version_id": v.parent_version_id,
        "redaction_summary": v.redaction_summary,
        "created_by": v.created_by, "created_at": v.created_at.isoformat(),
    }


def get_document(db: Session, user: User, document_id: int, request_id: str) -> dict:
    doc = _doc_or_404(db, document_id)
    require_case_access(db, user, doc.case_id, "view", request_id,
                        object_type="document", object_id=document_id)
    return document_to_dict(db, doc)


def list_versions(db: Session, user: User, document_id: int, request_id: str) -> list[dict]:
    doc = _doc_or_404(db, document_id)
    require_case_access(db, user, doc.case_id, "view", request_id,
                        object_type="document", object_id=document_id)
    rows = (
        db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        ).scalars().all()
    )
    return [version_to_dict(v) for v in rows]


def list_documents(db: Session, user: User, case_id: int, request_id: str,
                   limit: int, offset: int) -> tuple[list[dict], int]:
    require_case_access(db, user, case_id, "view", request_id)
    q = select(Document).where(Document.case_id == case_id)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = db.execute(q.order_by(Document.id).limit(limit).offset(offset)).scalars().all()
    return [document_to_dict(db, d) for d in rows], total


def download(
    db: Session, user: User, document_id: int, version_id: int | None, reason: str | None,
    request_id: str, storage: BaseStorage | None = None,
) -> tuple[bytes, str, str]:
    """Returns (plaintext_bytes, filename, mime_type)."""
    storage = storage or get_storage()
    doc = _doc_or_404(db, document_id)
    require_case_access(db, user, doc.case_id, "download", request_id,
                        object_type="document", object_id=document_id)
    if version_id is not None:
        version = db.get(DocumentVersion, version_id)
        if version is None or version.document_id != doc.id:
            raise NotFound("Version not found for this document")
    else:
        version = _current_version(db, doc)
    if version is None:
        raise BadRequest("Document has no version available for download")
    if not version.is_derivative and not reason:
        raise BadRequest("A reason is required to download an original version")

    plaintext = _decrypt_version(storage, version)
    ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png",
           "text/plain": "txt"}.get(version.mime_type, "bin")
    filename = f"doc-{doc.id}_v{version.version_number}.{ext}"

    write_audit(
        db, action="DOCUMENT_DOWNLOAD", outcome=AuditOutcome.ALLOWED, case_id=doc.case_id,
        actor_id=user.id, object_type="document_version", object_id=version.id,
        reason=reason or "derivative download", request_id=request_id,
    )
    db.commit()
    return plaintext, filename, version.mime_type


def verify(
    db: Session, user: User, document_id: int, request_id: str,
    storage: BaseStorage | None = None,
) -> dict:
    """Recompute SHA-256 over the decrypted current version. On mismatch:
    INCIDENT audit event + alert (via the alert center's INCIDENT filter)."""
    storage = storage or get_storage()
    doc = _doc_or_404(db, document_id)
    require_case_access(db, user, doc.case_id, "view", request_id,
                        object_type="document", object_id=document_id)
    version = _current_version(db, doc)
    if version is None:
        raise BadRequest("Document has no version to verify")

    try:
        computed = crypto.sha256_hex(_decrypt_version(storage, version))
    except Exception:
        computed = "DECRYPTION_FAILED"
    match = computed == version.sha256
    if match:
        write_audit(
            db, action="DOCUMENT_VERIFIED", outcome=AuditOutcome.ALLOWED, case_id=doc.case_id,
            actor_id=user.id, object_type="document_version", object_id=version.id,
            reason=f"integrity ok (sha256 {computed[:16]}…)", request_id=request_id,
        )
    else:
        write_audit(
            db, action="DOCUMENT_VERIFIED", outcome=AuditOutcome.INCIDENT, case_id=doc.case_id,
            actor_id=user.id, object_type="document_version", object_id=version.id,
            reason=f"INTEGRITY MISMATCH: stored {version.sha256[:16]}… vs computed {computed[:16]}…",
            request_id=request_id,
        )
    db.commit()
    return {
        "document_id": doc.id, "version_id": version.id,
        "stored_sha256": version.sha256, "computed_sha256": computed,
        "match": match, "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def freeze(db: Session, user: User, document_id: int, reason: str, request_id: str) -> dict:
    doc = _doc_or_404(db, document_id)
    require_case_access(db, user, doc.case_id, "freeze", request_id,
                        object_type="document", object_id=document_id)
    if doc.status not in (DocStatus.ACTIVE, DocStatus.UNDER_REVIEW):
        raise BadRequest(f"Only ACTIVE/UNDER_REVIEW documents can be frozen (is {doc.status.value})")
    if not reason:
        raise BadRequest("A reason is required to freeze a document")
    doc.status = DocStatus.FROZEN
    write_audit(
        db, action="DOCUMENT_FROZEN", outcome=AuditOutcome.ALLOWED, case_id=doc.case_id,
        actor_id=user.id, object_type="document", object_id=doc.id,
        reason=reason, request_id=request_id,
    )
    db.commit()
    return document_to_dict(db, doc)
