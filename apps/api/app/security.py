"""Passwords (bcrypt) and JWT (HS256)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_MINUTES = 30
REFRESH_TOKEN_DAYS = 7


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> tuple[str, int]:
    s = get_settings()
    expires_in = ACCESS_TOKEN_MINUTES * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int((now + timedelta(seconds=expires_in)).timestamp())},
        s.EABHILEKH_JWT_SECRET,
        algorithm="HS256",
    )
    return token, expires_in


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, get_settings().EABHILEKH_JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


def new_refresh_token() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
