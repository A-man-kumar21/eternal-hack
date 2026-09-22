"""Hash-chained audit log.

event_hash = sha256 of canonical JSON (sorted keys, no whitespace) of
{prev_hash, id, timestamp_utc, actor_id, action, case_id, object_id,
 outcome, reason, request_id}.

prev_hash = event_hash of the previous event for that case
(events with case_id NULL chain in a per-process 'GLOBAL' partition).
Genesis prev_hash = "GENESIS".

The business change and its audit event are always written in the SAME
DB transaction: callers flush, we compute hashes, then commit once.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AuditAnchor, AuditEvent, AuditOutcome, User

GENESIS = "GENESIS"
_GLOBAL_PARTITION = "__GLOBAL__"


def _norm_ts(ts: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC for hashing/comparison."""
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def _chain_key(case_id: int | None) -> str:
    return _GLOBAL_PARTITION if case_id is None else str(case_id)


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_event_hash(
    prev_hash: str,
    event_id: int,
    timestamp_utc: datetime,
    actor_id: int | None,
    action: str,
    case_id: int | None,
    object_id: str | None,
    outcome: str,
    reason: str | None,
    request_id: str,
) -> str:
    payload = {
        "prev_hash": prev_hash,
        "id": event_id,
        "timestamp_utc": _norm_ts(timestamp_utc).isoformat(),
        "actor_id": actor_id,
        "action": action,
        "case_id": case_id,
        "object_id": object_id,
        "outcome": outcome,
        "reason": reason,
        "request_id": request_id,
    }
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def last_event_hash(db: Session, case_id: int | None) -> str:
    q = select(AuditEvent.event_hash).order_by(AuditEvent.id.desc())
    if case_id is None:
        q = q.where(AuditEvent.case_id.is_(None))
    else:
        q = q.where(AuditEvent.case_id == case_id)
    row = db.execute(q.limit(1)).scalar()
    return row or GENESIS


def write_audit(
    db: Session,
    *,
    action: str,
    outcome: AuditOutcome | str,
    case_id: int | None = None,
    actor_id: int | None = None,
    object_type: str = "",
    object_id: str | int | None = None,
    reason: str | None = None,
    request_id: str,
) -> AuditEvent:
    """Create the audit row, link the hash chain, flush (no commit).

    Callers commit the transaction once their business change is also staged.
    """
    q = select(AuditEvent.event_hash).order_by(AuditEvent.id.desc())
    if case_id is None:
        q = q.where(AuditEvent.case_id.is_(None))
    else:
        q = q.where(AuditEvent.case_id == case_id)
    prev = db.execute(q.limit(1)).scalar() or GENESIS

    ev = AuditEvent(
        case_id=case_id,
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=None if object_id is None else str(object_id),
        outcome=AuditOutcome(outcome),
        reason=reason,
        request_id=request_id,
        prev_hash=prev,
        event_hash="",  # filled in after the id is assigned
    )
    db.add(ev)
    db.flush()  # assign id + created_at
    ev.event_hash = compute_event_hash(
        ev.prev_hash, ev.id, ev.created_at, ev.actor_id, ev.action,
        ev.case_id, ev.object_id, ev.outcome.value, ev.reason, ev.request_id,
    )
    db.flush()
    return ev


def verify_chain(db: Session, case_id: int) -> tuple[bool, int, int | None]:
    """Recompute every hash link for a case. Returns (ok, checked, broken_at_id)."""
    events = (
        db.execute(
            select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.id)
        )
        .scalars()
        .all()
    )
    prev = GENESIS
    for ev in events:
        expected = compute_event_hash(
            ev.prev_hash, ev.id, ev.created_at, ev.actor_id, ev.action,
            ev.case_id, ev.object_id, ev.outcome.value, ev.reason, ev.request_id,
        )
        if ev.prev_hash != prev or ev.event_hash != expected:
            return False, len(events), ev.id
        prev = ev.event_hash
    return True, len(events), None


def actor_display_name(db: Session, actor_id: int | None) -> str | None:
    if actor_id is None:
        return None
    u = db.get(User, actor_id)
    return u.display_name if u else None


def anchor_chain(db: Session, case_id: int, anchored_by: str = "anchor-job") -> AuditAnchor:
    """Snapshot a case's current chain head. Append-only: existing anchor rows
    are never updated or deleted. Same-transaction rules as write_audit —
    the caller commits once (here: immediately, the anchor is the whole change).
    """
    head = last_event_hash(db, case_id)
    count = (
        db.execute(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.case_id == case_id)
        ).scalar()
        or 0
    )
    row = AuditAnchor(
        case_id=case_id, anchored_hash=head, events_anchored=count, anchored_by=anchored_by
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def last_anchor(db: Session, case_id: int) -> AuditAnchor | None:
    return db.execute(
        select(AuditAnchor)
        .where(AuditAnchor.case_id == case_id)
        .order_by(AuditAnchor.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def check_anchor(db: Session, case_id: int) -> tuple[str | None, bool]:
    """Compare the live chain against the last anchor.

    Returns (last_anchored_hash, diverged). ``diverged`` is True when the
    first ``events_anchored`` events no longer hash to the anchored head —
    i.e. history was rewritten AND the hashes reforged (which plain
    verify_chain would miss). This is a more severe signal than a normal
    chain break. Legitimate appends after the anchor do NOT count as
    divergence: only the anchored prefix is compared.
    """
    anchor = last_anchor(db, case_id)
    if anchor is None:
        return None, False
    if anchor.events_anchored == 0:
        return anchor.anchored_hash, False
    nth_hash = db.execute(
        select(AuditEvent.event_hash)
        .where(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.id)
        .offset(anchor.events_anchored - 1)
        .limit(1)
    ).scalar()
    if nth_hash is None:
        return anchor.anchored_hash, True  # anchored events were deleted
    return anchor.anchored_hash, nth_hash != anchor.anchored_hash
