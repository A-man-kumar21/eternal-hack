"""Alerts (high-signal audit events) + case audit listing."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import actor_display_name
from ..models import AuditEvent, AuditOutcome, Case, CaseMember, Role, User
from .policy import require_case_access

ALERT_OUTCOMES = (AuditOutcome.DENIED, AuditOutcome.INCIDENT, AuditOutcome.FAILED)


def _event_to_dict(db: Session, a: AuditEvent) -> dict:
    case_number = None
    if a.case_id is not None:
        case = db.get(Case, a.case_id)
        case_number = case.case_number if case else None
    return {
        "id": a.id, "case_id": a.case_id, "case_number": case_number,
        "actor_id": a.actor_id, "actor_name": actor_display_name(db, a.actor_id),
        "action": a.action, "object_type": a.object_type, "object_id": a.object_id,
        "outcome": a.outcome.value, "reason": a.reason, "request_id": a.request_id,
        "created_at": a.created_at.isoformat(), "event_hash": a.event_hash,
        "prev_hash": a.prev_hash,
    }


def get_alerts(db: Session, user: User, limit: int, offset: int) -> tuple[list[dict], int]:
    q = select(AuditEvent).where(AuditEvent.outcome.in_(ALERT_OUTCOMES))
    if user.role != Role.SECURITY_AUDITOR:
        my_cases = select(CaseMember.case_id).where(CaseMember.user_id == user.id)
        q = q.where(AuditEvent.case_id.in_(my_cases))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = db.execute(q.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)).scalars().all()
    return [_event_to_dict(db, a) for a in rows], total


def case_audit(
    db: Session, user: User, case_id: int, request_id: str, limit: int, offset: int
) -> tuple[list[dict], int]:
    require_case_access(db, user, case_id, "audit_read", request_id)
    q = select(AuditEvent).where(AuditEvent.case_id == case_id)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = db.execute(q.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)).scalars().all()
    return [_event_to_dict(db, a) for a in rows], total
