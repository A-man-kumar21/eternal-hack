"""FastAPI dependencies: DB session, current user, request id."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import security
from ..db import get_session_factory
from ..errors import Unauthorized
from ..middleware import current_request_id
from ..models import User

_bearer = HTTPBearer(auto_error=False)
_bearer_optional = HTTPBearer(auto_error=False)


def get_db():
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise Unauthorized("Missing bearer token")
    user_id = security.decode_access_token(creds.credentials)
    if user_id is None:
        raise Unauthorized("Invalid or expired token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("User not found or inactive")
    return user


def get_request_id() -> str:
    return current_request_id()
