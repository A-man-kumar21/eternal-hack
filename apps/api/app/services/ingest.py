"""Document ingest pipeline.

The HTTP layer stages an upload (extension + size pre-checks, staged file
on disk, scan_jobs row). The background worker (workers/scan_worker.py)
calls process_pending() / process_job() here, which performs the full
validation chain: extension allowlist -> size -> MIME sniff -> SHA-256 ->
AV scan -> AES-256-GCM envelope encrypt -> object storage.

On success the document becomes ACTIVE with its first version; on
validation failure it becomes QUARANTINED with a reason. Business change
+ audit event are committed in ONE transaction.
"""
from __future__ import annotations

import os
import socket
import struct
import uuid
from pathlib import Path

import filetype
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import crypto
from ..audit import write_audit
from ..config import get_settings
from ..errors import BadRequest, TooLarge, Unprocessable
from ..models import (
    AuditOutcome,
    Document,
    DocumentVersion,
    DocStatus,
    DocType,
    ScanJob,
    ScanStatus,
    User,
)
from ..storage import BaseStorage, get_storage, new_object_key

EXT_TO_MIME = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "txt": "text/plain",
}


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_extension(filename: str) -> str:
    ext = _extension_of(filename)
    if ext not in get_settings().ALLOWED_EXTENSIONS:
        raise Unprocessable(
            f"Extension '.{ext}' not allowed; allowed: {sorted(get_settings().ALLOWED_EXTENSIONS)}"
        )
    return ext


def validate_size(num_bytes: int) -> None:
    if num_bytes > get_settings().MAX_UPLOAD_BYTES:
        raise TooLarge(f"Upload of {num_bytes} bytes exceeds 25 MB limit")


def sniff_mime(data: bytes, ext: str) -> str:
    """MIME sniff must match the extension family. Raises Unprocessable on mismatch."""
    if ext == "txt":
        # filetype has no signature for plain text; require UTF-8-decodable content
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Unprocessable("MIME mismatch: .txt content is not plain text") from exc
        return "text/plain"
    kind = filetype.guess(data)
    expected = EXT_TO_MIME[ext]
    if kind is None or kind.mime != expected:
        found = kind.mime if kind else "unknown"
        raise Unprocessable(f"MIME mismatch: .{ext} file sniffs as {found} (expected {expected})")
    return expected


def scan_with_clamav(data: bytes) -> dict:
    """Clamd INSTREAM scan. Graceful degradation: on any failure or when
    CLAMAV_HOST is unset, record skipped detail and continue."""
    s = get_settings()
    if not s.CLAMAV_HOST:
        return {"av": "skipped", "reason": "no AV service"}
    try:
        sock = socket.create_connection((s.CLAMAV_HOST, s.CLAMAV_PORT), timeout=10)
        try:
            sock.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 8192):
                chunk = data[i : i + 8192]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            resp = sock.recv(4096).decode("utf-8", errors="replace").strip()
        finally:
            sock.close()
        if "FOUND" in resp:
            return {"av": "positive", "detail": resp}
        return {"av": "clean", "detail": resp}
    except Exception as exc:  # graceful degradation
        return {"av": "skipped", "reason": f"clamd unreachable: {exc}"}


def stage_upload(
    db: Session,
    *,
    user: User,
    case_id: int,
    title: str,
    doc_type: DocType,
    description: str,
    file_bytes: bytes,
    original_filename: str,
    request_id: str,
) -> tuple[Document, ScanJob]:
    """HTTP-layer staging: fast pre-checks, then hand off to the worker."""
    ext = validate_extension(original_filename)  # 422 fast feedback
    validate_size(len(file_bytes))  # 413 fast feedback

    doc = Document(
        case_id=case_id, title=title, doc_type=doc_type,
        description=description or "", status=DocStatus.INGESTING, created_by=user.id,
    )
    db.add(doc)
    db.flush()

    staging = Path(get_settings().EABHILEKH_STAGING_DIR)
    staging.mkdir(parents=True, exist_ok=True)
    staged_name = f"{doc.id}_{uuid.uuid4().hex}.staging"
    (staging / staged_name).write_bytes(file_bytes)

    job = ScanJob(
        document_id=doc.id,
        status=ScanStatus.pending,
        detail={"original_filename": original_filename, "extension": ext, "staged_file": staged_name},
    )
    db.add(job)
    db.flush()
    write_audit(
        db, action="DOCUMENT_UPLOAD", outcome=AuditOutcome.ALLOWED, case_id=case_id,
        actor_id=user.id, object_type="document", object_id=doc.id,
        reason=f"staged '{original_filename}' for ingest", request_id=request_id,
    )
    db.commit()
    db.refresh(doc)
    db.refresh(job)
    return doc, job


def _quarantine(db: Session, doc: Document, job: ScanJob, reason: str, actor_id: int | None,
                case_id: int, request_id: str) -> None:
    doc.status = DocStatus.QUARANTINED
    doc.quarantine_reason = reason
    job.status = ScanStatus.done
    job.detail = {**(job.detail or {}), "result": "quarantined", "reason": reason}
    write_audit(
        db, action="DOCUMENT_QUARANTINED", outcome=AuditOutcome.FAILED, case_id=case_id,
        actor_id=actor_id, object_type="document", object_id=doc.id,
        reason=reason, request_id=request_id,
    )
    db.commit()


def process_job(db: Session, job_id: int, storage: BaseStorage | None = None,
                request_id: str | None = None) -> ScanJob:
    """Run the full ingest pipeline for one job. Idempotent per job."""
    storage = storage or get_storage()
    rid = request_id or f"worker-{job_id}-{uuid.uuid4().hex}"

    job = db.get(ScanJob, job_id)
    if job is None:
        raise BadRequest(f"scan job {job_id} not found")
    if job.status in (ScanStatus.done, ScanStatus.failed):
        return job  # idempotent: already handled
    if job.status == ScanStatus.processing:
        return job  # another worker holds it; leave alone

    job.status = ScanStatus.processing
    db.commit()  # claim

    doc = db.get(Document, job.document_id)
    case_id = doc.case_id
    actor_id = doc.created_by
    staged = Path(get_settings().EABHILEKH_STAGING_DIR) / (job.detail or {}).get("staged_file", "")
    try:
        if not staged.exists():
            raise Unprocessable("staged upload missing; cannot ingest")
        data = staged.read_bytes()
        original_filename = (job.detail or {}).get("original_filename", "")

        # 1. extension allowlist (defense in depth; route already checked)
        ext = validate_extension(original_filename)
        # 2. size
        validate_size(len(data))
        # 3. MIME sniff must match extension family
        mime = sniff_mime(data, ext)
        # 4. SHA-256 of plaintext
        plaintext_sha = crypto.sha256_hex(data)
        # 5. AV scan (graceful degradation)
        av = scan_with_clamav(data)
        if av.get("av") == "positive":
            _quarantine(db, doc, job, f"antivirus positive: {av.get('detail')}", actor_id, case_id, rid)
            return job

        # 6. envelope encrypt + store ciphertext
        enc = crypto.encrypt_blob(data)
        object_key = new_object_key("blobs")
        storage.put_bytes(object_key, bytes.fromhex(enc["ciphertext"]))

        # 7. version row + document ACTIVE — same transaction as the audit event
        version = DocumentVersion(
            document_id=doc.id, version_number=1, object_key=object_key,
            sha256=enc["sha256"], size_bytes=len(data), mime_type=mime,
            wrapped_dek=enc["wrapped_dek"], dek_nonce=enc["dek_nonce"],
            gcm_nonce=enc["gcm_nonce"], gcm_tag=enc["gcm_tag"],
            is_derivative=False, created_by=actor_id,
        )
        db.add(version)
        db.flush()
        doc.status = DocStatus.ACTIVE
        doc.current_version_id = version.id
        job.status = ScanStatus.done
        job.detail = {**(job.detail or {}), "result": "active", "version_id": version.id, "av": av}
        write_audit(
            db, action="DOCUMENT_INGESTED", outcome=AuditOutcome.ALLOWED, case_id=case_id,
            actor_id=actor_id, object_type="document", object_id=doc.id,
            reason=f"ingested v1 sha256={plaintext_sha[:16]}… av={av.get('av')}",
            request_id=rid,
        )
        db.commit()
        db.refresh(job)
        return job
    except (Unprocessable, TooLarge) as exc:
        db.rollback()
        doc = db.get(Document, job.document_id)
        job = db.get(ScanJob, job_id)
        _quarantine(db, doc, job, str(exc), actor_id, case_id, rid)
        return job
    except Exception as exc:  # unexpected failure: mark job failed, keep doc INGESTING
        db.rollback()
        job = db.get(ScanJob, job_id)
        job.status = ScanStatus.failed
        job.detail = {**(job.detail or {}), "result": "failed", "error": str(exc)}
        doc = db.get(Document, job.document_id)
        write_audit(
            db, action="DOCUMENT_INGESTED", outcome=AuditOutcome.FAILED, case_id=doc.case_id,
            actor_id=actor_id, object_type="document", object_id=doc.id,
            reason=f"ingest worker error: {exc}", request_id=rid,
        )
        db.commit()
        raise
    finally:
        try:
            if staged.exists():
                staged.unlink()
        except OSError:
            pass


def process_pending(db: Session, storage: BaseStorage | None = None, limit: int = 10) -> int:
    """Process up to `limit` pending jobs. Returns number handled."""
    ids = db.execute(
        select(ScanJob.id).where(ScanJob.status == ScanStatus.pending).order_by(ScanJob.id).limit(limit)
    ).scalars().all()
    for job_id in ids:
        try:
            process_job(db, job_id, storage)
        except Exception:
            continue  # job already marked failed inside process_job
    return len(ids)
