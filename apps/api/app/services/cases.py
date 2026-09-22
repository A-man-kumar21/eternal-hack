"""Case service."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..errors import Conflict, NotFound
from ..models import AuditOutcome, Case, CaseMember, Document, Role, User
from .policy import get_case_or_404, member_role, require_case_access, require_global_action


def create_case(db: Session, user: User, case_number: str, title: str, description: str, request_id: str) -> Case:
    require_global_action(db, user, "create_case", request_id)
    if db.execute(select(Case.id).where(Case.case_number == case_number)).scalar_one_or_none():
        raise Conflict(f"Case number {case_number} already exists")
    case = Case(case_number=case_number, title=title, description=description or "", created_by=user.id)
    db.add(case)
    db.flush()
    db.add(CaseMember(case_id=case.id, user_id=user.id, role=user.role, added_by=user.id))
    write_audit(
        db, action="CASE_CREATE", outcome=AuditOutcome.ALLOWED, case_id=case.id,
        actor_id=user.id, object_type="case", object_id=case.id,
        reason=f"case {case_number} created", request_id=request_id,
    )
    db.commit()
    db.refresh(case)
    return case


def list_cases(db: Session, user: User, limit: int, offset: int) -> tuple[list[Case], int]:
    if user.role == Role.SECURITY_AUDITOR:
        q = select(Case)
    else:
        q = select(Case).join(CaseMember, CaseMember.case_id == Case.id).where(
            CaseMember.user_id == user.id
        )
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = db.execute(q.order_by(Case.id).limit(limit).offset(offset)).scalars().all()
    return list(rows), total


def case_detail(db: Session, user: User, case_id: int, request_id: str) -> tuple[Case, list[dict], int]:
    case = require_case_access(db, user, case_id, "view", request_id)
    members = (
        db.execute(
            select(CaseMember, User).join(User, User.id == CaseMember.user_id)
            .where(CaseMember.case_id == case_id)
            .order_by(CaseMember.id)
        ).all()
    )
    member_list = [
        {"user_id": m.user_id, "username": u.username, "display_name": u.display_name, "role": m.role.value}
        for m, u in members
    ]
    doc_count = db.execute(
        select(func.count()).select_from(Document).where(Document.case_id == case_id)
    ).scalar() or 0
    return case, member_list, doc_count


def add_member(
    db: Session, user: User, case_id: int, target_user_id: int, role: Role, request_id: str
) -> CaseMember:
    case = require_case_access(db, user, case_id, "add_member", request_id, object_type="case_member")
    target = db.get(User, target_user_id)
    if target is None or not target.is_active:
        raise NotFound("User not found")
    if member_role(db, target_user_id, case_id) is not None:
        raise Conflict("User is already a member of this case")
    cm = CaseMember(case_id=case.id, user_id=target_user_id, role=role, added_by=user.id)
    db.add(cm)
    db.flush()
    write_audit(
        db, action="CASE_MEMBER_ADD", outcome=AuditOutcome.ALLOWED, case_id=case.id,
        actor_id=user.id, object_type="case_member", object_id=cm.id,
        reason=f"{target.username} added as {role.value}", request_id=request_id,
    )
    db.commit()
    db.refresh(cm)
    return cm
