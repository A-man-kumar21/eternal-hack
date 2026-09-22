from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..audit import anchor_chain, check_anchor, verify_chain
from ..models import Case, User
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
    anchored_hash, diverged = check_anchor(db, case_id)
    return {
        "ok": ok,
        "events_checked": checked,
        "broken_at_id": broken_at,
        "last_anchored_hash": anchored_hash,
        "anchor_diverged": diverged,
    }


@router.post("/audit/anchor", response_model=list[schemas.AnchorOut],
             status_code=status.HTTP_201_CREATED)
def anchor_chains(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    """Snapshot every case's audit chain head into the append-only anchor table.

    Intended to be called periodically (cron) with a SECURITY_AUDITOR
    credential, e.g.:
        curl -X POST https://api/audit/anchor -H "Authorization: Bearer $TOKEN"
    """
    from ..services.policy import require_global_action

    require_global_action(db, user, "anchor", rid)
    case_ids = db.execute(select(Case.id).order_by(Case.id)).scalars().all()
    out = []
    for cid in case_ids:
        row = anchor_chain(db, cid, anchored_by=f"anchor-job:{user.username}")
        out.append({
            "case_id": row.case_id,
            "anchored_hash": row.anchored_hash,
            "events_anchored": row.events_anchored,
            "anchored_at": row.created_at.isoformat(),
        })
    return out


@router.get("/alerts", response_model=schemas.AlertsOut)
def alerts(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    rows, _total = alerts_service.get_alerts(db, user, limit, offset)
    return {"alerts": [schemas.AuditEventOut(**r) for r in rows]}
