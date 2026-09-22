"""Case export bundles: encrypted ZIP with manifest.json + README.txt.

Synchronous build for the prototype (status flips to 'ready' before the
POST responds). The ZIP plaintext is envelope-encrypted and stored like
any other blob; download decrypts and streams it.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import crypto
from ..audit import last_event_hash, write_audit
from ..errors import BadRequest, NotFound, Unprocessable
from ..models import (
    AuditOutcome,
    Case,
    CustodyEvent,
    Document,
    DocumentVersion,
    DocStatus,
    ExportBundle,
    ExportStatus,
    User,
)
from ..storage import BaseStorage, get_storage, new_object_key
from .policy import require_case_access
from .redaction import _decrypt_version

MIME_TO_EXT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "text/plain": "txt",
}


def _safe_name(title: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._")[:80] or "document"
    return f"{base}.{ext}"


def _custody_summary(db: Session, document_id: int) -> list[dict]:
    rows = (
        db.execute(
            select(CustodyEvent).where(CustodyEvent.document_id == document_id).order_by(CustodyEvent.id)
        ).scalars().all()
    )
    return [
        {
            "action": r.action.value, "from_user_id": r.from_user_id,
            "to_user_id": r.to_user_id, "reason": r.reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def create_export(
    db: Session, user: User, case_id: int, document_ids: list[int], reason: str,
    request_id: str, storage: BaseStorage | None = None,
) -> ExportBundle:
    storage = storage or get_storage()
    case = require_case_access(db, user, case_id, "export", request_id)
    if not document_ids:
        raise BadRequest("document_ids must not be empty")

    docs: list[Document] = []
    for did in document_ids:
        doc = db.get(Document, did)
        if doc is None or doc.case_id != case_id:
            raise NotFound(f"Document {did} not found in this case")
        if doc.status not in (DocStatus.ACTIVE, DocStatus.FROZEN):
            raise Unprocessable(f"Document {did} is {doc.status.value}; only ACTIVE/FROZEN can be exported")
        if doc.current_version_id is None:
            raise Unprocessable(f"Document {did} has no current version")
        docs.append(doc)

    bundle = ExportBundle(case_id=case.id, status=ExportStatus.building, created_by=user.id)
    db.add(bundle)
    db.flush()
    write_audit(
        db, action="EXPORT_STARTED", outcome=AuditOutcome.ALLOWED, case_id=case.id,
        actor_id=user.id, object_type="export_bundle", object_id=bundle.id,
        reason=reason or f"export of {len(docs)} document(s)", request_id=request_id,
    )
    db.flush()

    try:
        zip_bytes = _build_zip(db, storage, case, bundle, docs, user, reason)
        enc = crypto.encrypt_blob(zip_bytes)
        object_key = new_object_key("exports")
        storage.put_bytes(object_key, bytes.fromhex(enc["ciphertext"]))
        bundle.object_key = object_key
        bundle.sha256 = enc["sha256"]  # sha256 of the ZIP plaintext (matches verify semantics)
        bundle.wrapped_dek = enc["wrapped_dek"]
        bundle.dek_nonce = enc["dek_nonce"]
        bundle.gcm_nonce = enc["gcm_nonce"]
        bundle.gcm_tag = enc["gcm_tag"]
        bundle.status = ExportStatus.ready
        write_audit(
            db, action="EXPORT_READY", outcome=AuditOutcome.ALLOWED, case_id=case.id,
            actor_id=user.id, object_type="export_bundle", object_id=bundle.id,
            reason=f"bundle ready; sha256={bundle.sha256}", request_id=request_id,
        )
    except Exception as exc:
        bundle.status = ExportStatus.failed
        bundle.manifest = {"error": str(exc)}
        write_audit(
            db, action="EXPORT_READY", outcome=AuditOutcome.FAILED, case_id=case.id,
            actor_id=user.id, object_type="export_bundle", object_id=bundle.id,
            reason=f"export build failed: {exc}", request_id=request_id,
        )
    db.commit()
    db.refresh(bundle)
    return bundle


def _build_zip(db: Session, storage: BaseStorage, case: Case, bundle: ExportBundle,
               docs: list[Document], user: User, reason: str) -> bytes:
    exported_at = datetime.now(timezone.utc).isoformat()
    manifest_docs = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            version = db.get(DocumentVersion, doc.current_version_id)
            plaintext = _decrypt_version(storage, version)
            ext = MIME_TO_EXT.get(version.mime_type, "bin")
            arcname = f"files/{doc.id}_{_safe_name(doc.title, ext)}"
            zf.writestr(arcname, plaintext)
            manifest_docs.append({
                "document_id": doc.id, "title": doc.title, "doc_type": doc.doc_type.value,
                "version_number": version.version_number, "sha256": version.sha256,
                "custody": _custody_summary(db, doc.id),
            })
        manifest = {
            "bundle_id": bundle.id,
            "case_number": case.case_number,
            "exported_at": exported_at,
            "exported_by": user.username,
            "audit_chain_head": last_event_hash(db, case.id),
            "documents": manifest_docs,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        zf.writestr("README.txt", (
            "e-Abhilekh export bundle — FICTIONAL DEMO DATA\n"
            f"Case: {case.case_number} — {case.title}\n"
            f"Exported at: {exported_at} by {user.username}\n"
            f"Reason: {reason or '-'}\n\n"
            "manifest.json describes every file, its SHA-256, custody history,\n"
            "and the head hash of the case audit chain at export time.\n"
        ))
    bundle.manifest = manifest
    return buf.getvalue()


def get_export(db: Session, user: User, bundle_id: int, request_id: str) -> ExportBundle:
    bundle = db.get(ExportBundle, bundle_id)
    if bundle is None:
        raise NotFound("Export bundle not found")
    require_case_access(db, user, bundle.case_id, "export", request_id,
                        object_type="export_bundle", object_id=bundle_id)
    return bundle


def download_export(
    db: Session, user: User, bundle_id: int, request_id: str,
    storage: BaseStorage | None = None,
) -> tuple[bytes, str]:
    """Returns (zip_plaintext_bytes, filename)."""
    storage = storage or get_storage()
    bundle = get_export(db, user, bundle_id, request_id)
    if bundle.status != ExportStatus.ready or not bundle.object_key:
        raise BadRequest("Bundle is not ready for download")
    ciphertext = storage.get_bytes(bundle.object_key)
    plaintext = crypto.decrypt_blob(
        ciphertext.hex(), bundle.wrapped_dek, bundle.dek_nonce, bundle.gcm_nonce, bundle.gcm_tag
    )
    if crypto.sha256_hex(plaintext) != bundle.sha256:
        write_audit(
            db, action="EXPORT_DOWNLOADED", outcome=AuditOutcome.INCIDENT, case_id=bundle.case_id,
            actor_id=user.id, object_type="export_bundle", object_id=bundle.id,
            reason="bundle integrity mismatch on download", request_id=request_id,
        )
        db.commit()
        raise BadRequest("Bundle integrity check failed")
    write_audit(
        db, action="EXPORT_DOWNLOADED", outcome=AuditOutcome.ALLOWED, case_id=bundle.case_id,
        actor_id=user.id, object_type="export_bundle", object_id=bundle.id,
        request_id=request_id,
    )
    db.commit()
    case = db.get(Case, bundle.case_id)
    return plaintext, f"e-abhilekh_{case.case_number}_bundle-{bundle.id}.zip"
