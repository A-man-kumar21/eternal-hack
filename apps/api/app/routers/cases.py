from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from .. import schemas
from ..models import Role, User
from ..services import cases as case_service
from .deps import get_current_user, get_db, get_request_id

router = APIRouter()


def _case_summary(c) -> schemas.CaseSummaryOut:
    return schemas.CaseSummaryOut(
        id=c.id, case_number=c.case_number, title=c.title, description=c.description,
        status=c.status, created_by=c.created_by, created_at=c.created_at.isoformat(),
    )


@router.post("/cases", response_model=schemas.CaseSummaryOut, status_code=status.HTTP_201_CREATED)
def create_case(
    body: schemas.CaseCreateIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    case = case_service.create_case(db, user, body.case_number, body.title, body.description, rid)
    return _case_summary(case)


@router.get("/cases", response_model=list[schemas.CaseOut])
def list_cases(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
    rid: str = Depends(get_request_id),
):
    # NOTE: returns the full CaseOut (members + document_count), not the slim
    # summary — the web client's case list renders member badges from it, and
    # an absent `members` array crashed the page (blank screen).
    rows, _total = case_service.list_cases(db, user, limit, offset)
    out = []
    for c in rows:
        case, members, doc_count = case_service.case_detail(db, user, c.id, rid)
        out.append(schemas.CaseOut(
            id=case.id, case_number=case.case_number, title=case.title,
            description=case.description, status=case.status, created_by=case.created_by,
            created_at=case.created_at.isoformat(),
            members=[schemas.MemberOut(**m) for m in members], document_count=doc_count,
        ))
    return out


@router.get("/cases/{case_id}", response_model=schemas.CaseOut)
def get_case(
    case_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    case, members, doc_count = case_service.case_detail(db, user, case_id, rid)
    return schemas.CaseOut(
        id=case.id, case_number=case.case_number, title=case.title, description=case.description,
        status=case.status, created_by=case.created_by, created_at=case.created_at.isoformat(),
        members=[schemas.MemberOut(**m) for m in members], document_count=doc_count,
    )


@router.post("/cases/{case_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    case_id: int, body: schemas.CaseMemberIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    cm = case_service.add_member(db, user, case_id, body.user_id, Role(body.role), rid)
    return {"id": cm.id, "case_id": cm.case_id, "user_id": cm.user_id, "role": cm.role.value}


@router.get("/cases/{case_id}/documents", response_model=list[schemas.DocumentOut])
def list_documents(
    case_id: int, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
    rid: str = Depends(get_request_id),
):
    from ..services import documents as doc_service
    rows, _total = doc_service.list_documents(db, user, case_id, rid, limit, offset)
    return [schemas.DocumentOut(**r) for r in rows]


@router.get("/cases/{case_id}/timeline", response_model=schemas.TimelineOut)
def timeline(
    case_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    from ..services import custody as custody_service
    return {"events": custody_service.timeline(db, user, case_id, rid)}


@router.get("/cases/{case_id}/audit", response_model=list[schemas.AuditEventOut])
def case_audit(
    case_id: int, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
    rid: str = Depends(get_request_id),
):
    from ..services import alerts as alerts_service
    rows, _total = alerts_service.case_audit(db, user, case_id, rid, limit, offset)
    return [schemas.AuditEventOut(**r) for r in rows]
