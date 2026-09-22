"""e-Abhilekh API application."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import ApiError
from .middleware import RequestIdMiddleware, request_id_ctx
from .routers import audit as audit_router
from .routers import auth as auth_router
from .routers import cases as cases_router
from .routers import dev as dev_router
from .routers import documents as documents_router

app = FastAPI(
    title="e-Abhilekh API",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)
app.add_middleware(RequestIdMiddleware)
# The React dev/preview frontend runs on :3000 and calls this API cross-origin.
# Without this, browsers block every request at the OPTIONS preflight (405).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _envelope(code: str, message: str, request_id: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id},
    )


def _rid(request: Request) -> str:
    return request_id_ctx.get() or "unknown"


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return _envelope(exc.code, exc.detail, _rid(request), exc.status_code)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    code = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN",
            404: "NOT_FOUND", 409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE",
            422: "VALIDATION_ERROR"}.get(exc.status_code, "ERROR")
    return _envelope(code, str(exc.detail), _rid(request), exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return _envelope("VALIDATION_ERROR", str(exc.errors()), _rid(request), 422)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    return _envelope("INTERNAL_ERROR", "Internal server error", _rid(request), 500)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.include_router(auth_router.router, prefix="/api/v1", tags=["auth"])
app.include_router(cases_router.router, prefix="/api/v1", tags=["cases"])
app.include_router(documents_router.router, prefix="/api/v1", tags=["documents"])
app.include_router(audit_router.router, prefix="/api/v1", tags=["audit"])
app.include_router(dev_router.router, prefix="/api/v1", tags=["dev"])
