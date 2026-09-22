from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..audit import verify_chain
from ..models import User
from ..services import alerts as alerts_service
from .deps import get_current_user, get_db, get_request_id

router = APIRouter()


@router.get("/audit/verify-chain", response_model=schemas.VerifyChainOut)
def verify_chain_route(
    case_id: int = Query(...), db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    from ..services.policy import require_case_access

    require_case_access(db, user, case_id, "audit_read", rid)
    ok, checked, broken_at = verify_chain(db, case_id)
    return {"ok": ok, "events_checked": checked, "broken_at_id": broken_at}


@router.get("/alerts", response_model=schemas.AlertsOut)
def alerts(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    rows, _total = alerts_service.get_alerts(db, user, limit, offset)
    return {"alerts": [schemas.AuditEventOut(**r) for r in rows]}
