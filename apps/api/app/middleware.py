"""Request-ID middleware + contextvar so services can audit with it."""
from __future__ import annotations

import contextvars
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request_id_ctx.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


def current_request_id() -> str:
    return request_id_ctx.get() or uuid.uuid4().hex
