"""Auth service: login / refresh rotation / logout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..audit import write_audit
from ..errors import Unauthorized
from ..models import AuditOutcome, RefreshToken, User


def _get_active_user(db: Session, username: str) -> User | None:
    return db.execute(
        select(User).where(User.username == username, User.is_active.is_(True))
    ).scalar_one_or_none()


def login(db: Session, username: str, password: str, request_id: str) -> dict:
    user = _get_active_user(db, username)
    if user is None or not security.verify_password(password, user.password_hash):
        write_audit(
            db, action="AUTH_LOGIN", outcome=AuditOutcome.FAILED, actor_id=None,
            object_type="user", object_id=username, reason="invalid credentials",
            request_id=request_id,
        )
        db.commit()
        raise Unauthorized("Invalid username or password")

    access_token, expires_in = security.create_access_token(user.id)
    refresh = security.new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=security.hash_token(refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=security.REFRESH_TOKEN_DAYS),
        )
    )
    write_audit(
        db, action="AUTH_LOGIN", outcome=AuditOutcome.ALLOWED, actor_id=user.id,
        object_type="user", object_id=user.id, request_id=request_id,
    )
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user,
    }


def refresh(db: Session, refresh_token: str, request_id: str) -> dict:
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == security.hash_token(refresh_token))
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expires = row.expires_at if row is None else (
        row.expires_at if row.expires_at.tzinfo is not None
        else row.expires_at.replace(tzinfo=timezone.utc)
    )
    if row is None or row.revoked or expires < now:
        write_audit(
            db, action="AUTH_REFRESH", outcome=AuditOutcome.FAILED, actor_id=None,
            object_type="refresh_token", reason="invalid or expired refresh token",
            request_id=request_id,
        )
        db.commit()
        raise Unauthorized("Invalid refresh token")

    # rotation: revoke the presented token, issue a new pair
    row.revoked = True
    access_token, expires_in = security.create_access_token(row.user_id)
    new_refresh = security.new_refresh_token()
    db.add(
        RefreshToken(
            user_id=row.user_id,
            token_hash=security.hash_token(new_refresh),
            expires_at=now + timedelta(days=security.REFRESH_TOKEN_DAYS),
        )
    )
    user = db.get(User, row.user_id)
    write_audit(
        db, action="AUTH_REFRESH", outcome=AuditOutcome.ALLOWED, actor_id=row.user_id,
        object_type="user", object_id=row.user_id, request_id=request_id,
    )
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user,
    }


def logout(db: Session, refresh_token: str, request_id: str) -> None:
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == security.hash_token(refresh_token))
    ).scalar_one_or_none()
    if row is not None:
        row.revoked = True
        write_audit(
            db, action="AUTH_LOGOUT", outcome=AuditOutcome.ALLOWED, actor_id=row.user_id,
            object_type="user", object_id=row.user_id, request_id=request_id,
        )
        db.commit()
    # Idempotent: unknown token -> still 204, nothing to revoke.
