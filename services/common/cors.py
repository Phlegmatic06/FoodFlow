"""CORS configuration helper for FoodFlow FastAPI services."""

from __future__ import annotations

import os
from typing import Sequence
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

DEFAULT_CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

DEFAULT_CORS_HEADERS = [
    "Content-Type",
    "X-Request-ID",
    "X-Guest-Session-ID",
    "Authorization",
    "Accept",
    "Origin",
    "X-Requested-With",
]


def get_cors_origins() -> list[str]:
    """Retrieve allowed CORS origins from environment or default to local dev URLs."""
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return list(DEFAULT_CORS_ORIGINS)


def configure_cors(
    app: FastAPI,
    *,
    allow_origins: Sequence[str] | None = None,
    allow_methods: Sequence[str] | None = None,
    allow_headers: Sequence[str] | None = None,
    allow_credentials: bool = False,
) -> None:
    """Register FastAPI CORSMiddleware with project-wide defaults.
    
    Uses explicit allowed headers and disallows credentialed requests by default.
    """
    origins = list(allow_origins) if allow_origins is not None else get_cors_origins()
    methods = list(allow_methods) if allow_methods is not None else DEFAULT_CORS_METHODS
    headers = list(allow_headers) if allow_headers is not None else list(DEFAULT_CORS_HEADERS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=methods,
        allow_headers=headers,
        expose_headers=["X-Request-ID"],
    )
