"""Consistent error response handlers conforming to OpenAPI contract specifications."""

from __future__ import annotations

import uuid
from typing import Any, List
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.common.models import ErrorDetail, ErrorResponse


def get_request_id(request: Request) -> str:
    """Extract X-Request-ID header or generate a new random identifier."""
    return request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:8]}"


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard FastAPI/Starlette HTTP exceptions."""
    req_id = get_request_id(request)
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", f"HTTP_{exc.status_code}")
        message = exc.detail.get("message", "Error")
        raw_details = exc.detail.get("details", [message])
        details = raw_details if isinstance(raw_details, list) else [str(raw_details)]
    else:
        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        code = f"HTTP_{exc.status_code}"
        message = detail_msg
        details = [detail_msg]

    error_payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            request_id=req_id,
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload.model_dump(),
        headers={"X-Request-ID": req_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request schema and validation errors with HTTP 400 per OpenAPI contracts."""
    req_id = get_request_id(request)
    details: List[Any] = []
    for err in exc.errors():
        loc_parts = [str(x) for x in err.get("loc", []) if str(x) not in ("body", "query", "path")]
        loc = ".".join(loc_parts) or "parameter"
        msg = err.get("msg", "Invalid value")
        details.append({"field": loc, "issue": msg})

    error_payload = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Request parameters failed validation",
            details=details,
            request_id=req_id,
        )
    )
    return JSONResponse(
        status_code=400,
        content=error_payload.model_dump(),
        headers={"X-Request-ID": req_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected internal server errors."""
    req_id = get_request_id(request)
    error_payload = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred",
            details=[],
            request_id=req_id,
        )
    )
    return JSONResponse(
        status_code=500,
        content=error_payload.model_dump(),
        headers={"X-Request-ID": req_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach standard FoodFlow exception handlers to a FastAPI application instance."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

