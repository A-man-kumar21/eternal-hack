"""Service-layer authorization.

All authorization decisions live here, NOT in routers. Every denial
writes a DENIED audit event (same transaction rules as normal audit
writes) so denied attempts surface in the auditor's alert center.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..errors import Forbidden, NotFound
from ..models import AuditOutcome, Case, CaseMember, Role, User

# action -> roles allowed (must ALSO be a case member, except auditor global reads)
ACTION_ROLES: dict[str, set[Role]] = {
    "create_case": {Role.INVESTIGATOR, Role.LEGAL_REVIEWER, Role.EVIDENCE_CUSTODIAN, Role.SECURITY_AUDITOR},
    "add_member": {Role.INVESTIGATOR, Role.EVIDENCE_CUSTODIAN},
    "upload": {Role.INVESTIGATOR, Role.EVIDENCE_CUSTODIAN},
    "view": {Role.INVESTIGATOR, Role.LEGAL_REVIEWER, Role.EVIDENCE_CUSTODIAN, Role.SECURITY_AUDITOR},
    "download": {Role.INVESTIGATOR, Role.LEGAL_REVIEWER, Role.EVIDENCE_CUSTODIAN, Role.SECURITY_AUDITOR},
    "custody_handoff": {Role.INVESTIGATOR},
    "custody_accept": {Role.EVIDENCE_CUSTODIAN},
    "custody_release": {Role.INVESTIGATOR, Role.EVIDENCE_CUSTODIAN},
    "freeze": {Role.EVIDENCE_CUSTODIAN},
    "redact": {Role.LEGAL_REVIEWER, Role.EVIDENCE_CUSTODIAN},
    "export": {Role.LEGAL_REVIEWER, Role.EVIDENCE_CUSTODIAN},
    "audit_read": {Role.INVESTIGATOR, Role.LEGAL_REVIEWER, Role.EVIDENCE_CUSTODIAN, Role.SECURITY_AUDITOR},
    "anchor": {Role.SECURITY_AUDITOR},
}

# Actions that are forbidden once a case is CLOSED, regardless of the caller's
# role. Reads (view/download/audit_read), custody_release and export stay
# available so closed cases remain reviewable and releasable.
CLOSED_BLOCKED_ACTIONS: set[str] = {
    "upload",
    "redact",
    "custody_handoff",
    "custody_accept",
    "freeze",
    "add_member",
}

# attempted action -> audit action name used on DENIED events
AUDIT_ACTION_FOR = {
    "create_case": "CASE_CREATE",
    "add_member": "CASE_MEMBER_ADD",
    "upload": "DOCUMENT_UPLOAD",
    "view": "CASE_READ",
    "download": "DOCUMENT_DOWNLOAD",
    "custody_handoff": "CUSTODY_HANDOFF",
    "custody_accept": "CUSTODY_ACCEPT",
    "custody_release": "CUSTODY_RELEASE",
    "freeze": "DOCUMENT_FREEZE",
    "redact": "REDACTION_APPLY",
    "export": "EXPORT_CREATE",
    "audit_read": "AUDIT_READ",
    "anchor": "AUDIT_ANCHOR",
}


def deny(
    db: Session,
    *,
    user: User,
    action: str,
    case_id: int | None,
    object_type: str = "",
    object_id: str | int | None = None,
    reason: str,
    request_id: str,
) -> None:
    """Write a DENIED audit event and raise 403. Never returns."""
    write_audit(
        db,
        action=AUDIT_ACTION_FOR.get(action, action.upper()),
        outcome=AuditOutcome.DENIED,
        case_id=case_id,
        actor_id=user.id,
        object_type=object_type,
        object_id=object_id,
        reason=reason,
        request_id=request_id,
    )
    db.commit()
    raise Forbidden(reason)


def get_case_or_404(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFound("Case not found")
    return case


def member_role(db: Session, user_id: int, case_id: int) -> Role | None:
    row = db.execute(
        select(CaseMember.role).where(CaseMember.case_id == case_id, CaseMember.user_id == user_id)
    ).scalar()
    return row


def require_case_access(
    db: Session,
    user: User,
    case_id: int,
    action: str,
    request_id: str,
    *,
    object_type: str = "case",
    object_id: str | int | None = None,
) -> Case:
    """Enforce: case exists, case is not CLOSED for mutating actions, caller is
    a member (or auditor on audit reads), and the caller's role is permitted
    for `action`.

    Returns the Case. Raises 403 (with DENIED audit) or 404.
    """
    case = get_case_or_404(db, case_id)
    if case.status == "CLOSED" and action in CLOSED_BLOCKED_ACTIONS:
        deny(
            db, user=user, action=action, case_id=case_id,
            object_type=object_type, object_id=object_id or case_id,
            reason=f"forbidden: case {case.case_number} is CLOSED; '{action}' is blocked on closed cases",
            request_id=request_id,
        )
    is_auditor = user.role == Role.SECURITY_AUDITOR
    auditor_global = is_auditor and action in {"audit_read", "view"}

    mrole = member_role(db, user.id, case_id)
    if mrole is None and not auditor_global:
        deny(
            db, user=user, action=action, case_id=case_id,
            object_type=object_type, object_id=object_id or case_id,
            reason=f"forbidden: {user.username} is not a member of case {case.case_number}",
            request_id=request_id,
        )
    effective_role = mrole or user.role  # auditor global reads use their own role
    if effective_role not in ACTION_ROLES[action]:
        deny(
            db, user=user, action=action, case_id=case_id,
            object_type=object_type, object_id=object_id or case_id,
            reason=f"forbidden: role {effective_role.value} may not perform '{action}'",
            request_id=request_id,
        )
    return case


def require_global_action(db: Session, user: User, action: str, request_id: str) -> None:
    """For non-case actions like create_case."""
    if user.role not in ACTION_ROLES[action]:
        write_audit(
            db, action=AUDIT_ACTION_FOR.get(action, action.upper()),
            outcome=AuditOutcome.DENIED, actor_id=user.id,
            reason=f"forbidden: role {user.role.value} may not perform '{action}'",
            request_id=request_id,
        )
        db.commit()
        raise Forbidden(f"Role {user.role.value} may not perform '{action}'")
