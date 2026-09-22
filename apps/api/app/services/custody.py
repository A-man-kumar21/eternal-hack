"""Custody chain + case timeline."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import actor_display_name, write_audit
from ..errors import BadRequest, NotFound
from ..models import AuditEvent, AuditOutcome, CustodyAction, CustodyEvent, Document, User
from .policy import member_role, require_case_access

ACTION_FOR = {
    "handoff": "custody_handoff",
    "accept": "custody_accept",
    "release": "custody_release",
}


def record_custody(
    db: Session, user: User, document_id: int, action: str, to_user_id: int | None,
    reason: str, request_id: str,
) -> CustodyEvent:
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document not found")
    if action not in ACTION_FOR:
        raise BadRequest("action must be handoff|accept|release")
    require_case_access(db, user, doc.case_id, ACTION_FOR[action], request_id,
                        object_type="document", object_id=document_id)

    to_user = None
    if action == "handoff":
        if to_user_id is None:
            raise BadRequest("to_user_id is required for handoff")
        to_user = db.get(User, to_user_id)
        if to_user is None or not to_user.is_active:
            raise NotFound("Target user not found")
        if member_role(db, to_user_id, doc.case_id) is None:
            raise BadRequest("Custody can only be handed to a case member")
    elif action == "accept":
        to_user_id = to_user_id or user.id

    ev = CustodyEvent(
        document_id=doc.id, action=CustodyAction(action),
        from_user_id=user.id, to_user_id=to_user_id, reason=reason or "",
    )
    db.add(ev)
    db.flush()
    write_audit(
        db, action=f"CUSTODY_{action.upper()}", outcome=AuditOutcome.ALLOWED,
        case_id=doc.case_id, actor_id=user.id, object_type="custody_event", object_id=ev.id,
        reason=reason or f"{action} of document {doc.id}"
        + (f" to {to_user.username}" if to_user else ""),
        request_id=request_id,
    )
    db.commit()
    db.refresh(ev)
    return ev


_KIND_FOR_ACTION = {
    "DOCUMENT_INGESTED": "ingest",
    "DOCUMENT_QUARANTINED": "ingest",
    "DOCUMENT_UPLOAD": "ingest",
    "DOCUMENT_VERIFIED": "verify",
    "DOCUMENT_VERIFY": "verify",
    "REDACTION_ANALYZED": "redaction",
    "REDACTION_APPLIED": "redaction",
    "EXPORT_STARTED": "export",
    "EXPORT_READY": "export",
    "EXPORT_DOWNLOADED": "export",
    "CUSTODY_HANDOFF": "custody",
    "CUSTODY_ACCEPT": "custody",
    "CUSTODY_RELEASE": "custody",
}


def timeline(db: Session, user: User, case_id: int, request_id: str, limit: int = 200) -> list[dict]:
    require_case_access(db, user, case_id, "view", request_id)
    events: list[dict] = []

    audit_rows = (
        db.execute(
            select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.id.desc()).limit(limit)
        ).scalars().all()
    )
    for a in audit_rows:
        events.append({
            "id": f"audit-{a.id}", "kind": _KIND_FOR_ACTION.get(a.action, "audit"),
            "actor": actor_display_name(db, a.actor_id), "action": a.action,
            "object_id": a.object_id, "reason": a.reason,
            "created_at": a.created_at.isoformat(), "detail": {"outcome": a.outcome.value},
        })

    custody_rows = (
        db.execute(
            select(CustodyEvent, Document.title)
            .join(Document, Document.id == CustodyEvent.document_id)
            .where(Document.case_id == case_id)
            .order_by(CustodyEvent.id.desc())
            .limit(limit)
        ).all()
    )
    for c, title in custody_rows:
        events.append({
            "id": f"custody-{c.id}", "kind": "custody",
            "actor": actor_display_name(db, c.from_user_id), "action": f"CUSTODY_{c.action.value.upper()}",
            "object_id": str(c.document_id), "reason": c.reason,
            "created_at": c.created_at.isoformat(),
            "detail": {"document_title": title, "to_user_id": c.to_user_id},
        })

    events.sort(key=lambda e: e["created_at"])
    return events[:limit]
