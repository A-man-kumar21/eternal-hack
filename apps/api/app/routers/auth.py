from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .. import schemas
from ..models import User
from ..services import auth as auth_service
from .deps import _bearer_optional, get_current_user, get_db, get_request_id

router = APIRouter()


def _user_out(u: User) -> schemas.UserOut:
    return schemas.UserOut(id=u.id, username=u.username, display_name=u.display_name, role=u.role.value)


@router.post("/auth/login", response_model=schemas.TokenPairOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db), rid: str = Depends(get_request_id)):
    res = auth_service.login(db, body.username, body.password, rid)
    return {**{k: v for k, v in res.items() if k != "user"}, "user": _user_out(res["user"])}


@router.post("/auth/refresh", response_model=schemas.TokenPairOut)
def refresh(body: schemas.RefreshIn, db: Session = Depends(get_db), rid: str = Depends(get_request_id)):
    res = auth_service.refresh(db, body.refresh_token, rid)
    return {**{k: v for k, v in res.items() if k != "user"}, "user": _user_out(res["user"])}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: schemas.LogoutIn | None = None,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
    db: Session = Depends(get_db), rid: str = Depends(get_request_id),
):
    # Accept the refresh token either in the JSON body ({"refresh_token": ...})
    # or as the Authorization bearer token.
    token = (body.refresh_token if body else None) or (creds.credentials if creds else None)
    if token:
        auth_service.logout(db, token, rid)
    return None


@router.get("/users/me", response_model=schemas.UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..models import User as U
    rows = db.query(U).filter(U.is_active.is_(True)).order_by(U.id).all()
    return [_user_out(u) for u in rows]
