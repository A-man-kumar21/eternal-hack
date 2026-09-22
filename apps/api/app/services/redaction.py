"""P1 redaction: rules-based PII detection + leak-safe derivative PDFs.

SIMPLIFICATION (documented in README): text-based PDFs have no reliable
per-glyph coordinates, so marks carry bbox=null and the frontend shows a
textual list. The derivative PDF is a freshly rendered document: a cover
page stating the redaction summary, followed by the extracted text with
every APPROVED span replaced by black bars ("██████"). The original
version is never modified. A leak check asserts no approved plaintext
span survives in the derivative.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import crypto
from ..audit import write_audit
from ..errors import BadRequest, NotFound
from ..models import (
    AuditOutcome,
    Document,
    DocumentVersion,
    RedactionMark,
    RedactionStatus,
    User,
)
from ..storage import BaseStorage, get_storage, new_object_key
from .policy import require_case_access

AADHAAR_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
PHONE_RE = re.compile(r"\b[6-9]\d{9}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

RULES = [
    ("AADHAAR", AADHAAR_RE, 0.95),
    ("PHONE", PHONE_RE, 0.90),
    ("EMAIL", EMAIL_RE, 0.85),
]

BLOCK = "█"


def _decrypt_version(storage: BaseStorage, version: DocumentVersion) -> bytes:
    return crypto.decrypt_blob(
        storage.get_bytes(version.object_key).hex(),
        version.wrapped_dek, version.dek_nonce, version.gcm_nonce, version.gcm_tag,
    )


def extract_pages(data: bytes, mime: str) -> tuple[list[str], str | None]:
    """Returns (page_texts, note). note='ocr_required' when nothing extractable."""
    if mime == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [(p.extract_text() or "") for p in reader.pages]
        except Exception:
            return [], "ocr_required"
        if not any(t.strip() for t in pages):
            return [], "ocr_required"
        return pages, None
    if mime.startswith("image/"):
        try:
            import pytesseract  # optional
            from PIL import Image

            text = pytesseract.image_to_string(Image.open(io.BytesIO(data)))
            return [text], None
        except Exception:
            return [], "ocr_unavailable"
    if mime == "text/plain":
        return [data.decode("utf-8", errors="replace")], None
    return [], "unsupported_type"


def _excerpt(text: str, start: int, end: int, ctx: int = 30) -> str:
    s = max(0, start - ctx)
    e = min(len(text), end + ctx)
    return ("…" if s > 0 else "") + text[s:e] + ("…" if e < len(text) else "")


def analyze(
    db: Session, user: User, document_id: int, request_id: str,
    storage: BaseStorage | None = None,
) -> dict:
    storage = storage or get_storage()
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document not found")
    require_case_access(db, user, doc.case_id, "redact", request_id,
                        object_type="document", object_id=document_id)
    version = db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
    if version is None:
        raise BadRequest("Document has no ingested version yet")

    plaintext = _decrypt_version(storage, version)
    pages, note = extract_pages(plaintext, version.mime_type)

    # re-analysis replaces prior proposed marks for this version (idempotent)
    db.query(RedactionMark).filter(
        RedactionMark.document_version_id == version.id,
        RedactionMark.status == RedactionStatus.proposed,
    ).delete()
    db.flush()

    marks: list[RedactionMark] = []
    for page_idx, text in enumerate(pages):
        for label, pattern, confidence in RULES:
            for m in pattern.finditer(text):
                marks.append(
                    RedactionMark(
                        document_version_id=version.id, page=page_idx + 1, bbox=None,
                        label=label, confidence=confidence,
                        text_excerpt=_excerpt(text, m.start(), m.end()),
                        matched_text=m.group(0),
                        status=RedactionStatus.proposed,
                    )
                )
                db.add(marks[-1])
    db.flush()

    write_audit(
        db, action="REDACTION_ANALYZED", outcome=AuditOutcome.ALLOWED, case_id=doc.case_id,
        actor_id=user.id, object_type="document", object_id=doc.id,
        reason=f"{len(marks)} marks proposed on v{version.version_number}"
        + (f" (note: {note})" if note else ""),
        request_id=request_id,
    )
    db.commit()

    return {
        "version_id": version.id,
        "marks": [
            {
                "mark_id": m.id, "page": m.page, "bbox": m.bbox, "label": m.label,
                "confidence": m.confidence, "text_excerpt": m.text_excerpt,
            }
            for m in marks
        ],
        **({"note": note} if note else {}),
    }


def _render_derivative_pdf(cover_lines: list[str], pages: list[str], approved_spans: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 48
    usable = width - 2 * margin

    def draw_wrapped(lines: list[str], y_start: float) -> float:
        y = y_start
        for line in lines:
            words, cur = line.split(), ""
            for w in words:
                trial = f"{cur} {w}".strip()
                if c.stringWidth(trial, "Helvetica", 10) > usable and cur:
                    c.drawString(margin, y, cur)
                    y -= 14
                    cur = w
                else:
                    cur = trial
            if cur:
                c.drawString(margin, y, cur)
                y -= 14
            if y < margin:
                c.showPage()
                y = height - margin
        return y

    y = height - margin
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "REDACTED DERIVATIVE — FICTIONAL DEMO DATA")
    y -= 22
    c.setFont("Helvetica", 10)
    y = draw_wrapped(cover_lines, y)
    y -= 10

    for i, page_text in enumerate(pages):
        redacted = page_text
        for span in approved_spans:
            if span in redacted:
                redacted = redacted.replace(span, BLOCK * max(6, len(span)))
        y -= 8
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, f"--- page {i + 1} (redacted) ---")
        y -= 16
        c.setFont("Helvetica", 10)
        y = draw_wrapped(redacted.splitlines() or [""], y)
        c.showPage()
        y = height - margin
    c.save()
    return buf.getvalue()


def apply_approvals(
    db: Session, user: User, document_id: int, approvals: list[dict], request_id: str,
    storage: BaseStorage | None = None,
) -> DocumentVersion:
    storage = storage or get_storage()
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document not found")
    require_case_access(db, user, doc.case_id, "redact", request_id,
                        object_type="document", object_id=document_id)
    version = db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
    if version is None:
        raise BadRequest("Document has no ingested version yet")

    approved_spans: list[str] = []
    for item in approvals:
        mark = db.get(RedactionMark, item["mark_id"])
        if mark is None or mark.document_version_id != version.id:
            raise BadRequest(f"Unknown mark {item['mark_id']} for this version")
        if mark.status != RedactionStatus.proposed:
            raise BadRequest(f"Mark {mark.id} already reviewed")
        if item.get("approved"):
            mark.status = RedactionStatus.approved
            approved_spans.append(mark.matched_text or _exact_span(mark.text_excerpt))
        else:
            mark.status = RedactionStatus.rejected
        mark.reviewed_by = user.id
    db.flush()

    plaintext = _decrypt_version(storage, version)
    pages, _ = extract_pages(plaintext, version.mime_type)

    cover = [
        f"Parent version: v{version.version_number} (sha256 {version.sha256})",
        f"Redacted by: {user.display_name} ({user.username})",
        f"Redacted at: {datetime.now(timezone.utc).isoformat()}",
        f"Marks approved: {len(approved_spans)}",
        "Method: text-replacement derivative (approved spans replaced by black bars).",
        "Original version is untouched and remains the evidentiary source.",
    ]
    derivative_pdf = _render_derivative_pdf(cover, pages, approved_spans)

    # LEAK CHECK: no approved plaintext span may appear in the derivative
    derivative_text = "\n".join(extract_pages(derivative_pdf, "application/pdf")[0])
    for span in approved_spans:
        if span and (span in derivative_text or span.encode() in derivative_pdf):
            raise BadRequest("Leak check failed: approved span present in derivative")

    enc = crypto.encrypt_blob(derivative_pdf)
    object_key = new_object_key("blobs")
    storage.put_bytes(object_key, bytes.fromhex(enc["ciphertext"]))
    max_vn = db.execute(
        select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == doc.id)
    ).scalar() or 0
    deriv = DocumentVersion(
        document_id=doc.id, version_number=max_vn + 1, object_key=object_key,
        sha256=enc["sha256"], size_bytes=len(derivative_pdf), mime_type="application/pdf",
        wrapped_dek=enc["wrapped_dek"], dek_nonce=enc["dek_nonce"],
        gcm_nonce=enc["gcm_nonce"], gcm_tag=enc["gcm_tag"],
        is_derivative=True, parent_version_id=version.id,
        # server-generated from the already-scanned parent bytes: no new
        # untrusted input, so the AV status carries over
        av_status=version.av_status, av_detail=version.av_detail,
        redaction_summary={
            "parent_version_id": version.id,
            "marks_approved": len(approved_spans),
            "method": "text-replacement",
            "note": "bbox unavailable for text PDFs; marks listed textually",
        },
        created_by=user.id,
    )
    db.add(deriv)
    db.flush()
    write_audit(
        db, action="REDACTION_APPLIED", outcome=AuditOutcome.ALLOWED, case_id=doc.case_id,
        actor_id=user.id, object_type="document_version", object_id=deriv.id,
        reason=f"derivative v{deriv.version_number} from v{version.version_number}; "
               f"{len(approved_spans)} spans redacted",
        request_id=request_id,
    )
    db.commit()
    db.refresh(deriv)
    return deriv


def _exact_span(excerpt: str) -> str:
    """Recover the exact matched span from the excerpt: the regex match is the
    longest token run matching one of the RULES inside the excerpt."""
    best = ""
    for _, pattern, _ in RULES:
        for m in pattern.finditer(excerpt):
            if len(m.group(0)) > len(best):
                best = m.group(0)
    return best


def list_derivatives(db: Session, user: User, document_id: int, request_id: str) -> list[DocumentVersion]:
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document not found")
    require_case_access(db, user, doc.case_id, "view", request_id,
                        object_type="document", object_id=document_id)
    return list(
        db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id, DocumentVersion.is_derivative.is_(True))
            .order_by(DocumentVersion.version_number.desc())
        ).scalars()
    )
