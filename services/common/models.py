"""Common Pydantic data models for FoodFlow backend services."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Standard OpenAPI health probe response model."""

    status: str = Field(..., example="healthy")
    service: str = Field(..., example="profile-nutrition")
    version: str = Field(..., example="0.1.0")


class DatabaseReadinessInfo(BaseModel):
    """Database connectivity status details for readiness check."""

    connected: bool
    user: Optional[str] = None
    schema_name: Optional[str] = Field(None, alias="schema")
    database: Optional[str] = None
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


class ReadinessResponse(BaseModel):
    """Readiness probe response including database subsystem status."""

    status: str = Field(..., example="ready")
    service: str = Field(..., example="profile-nutrition")
    version: str = Field(..., example="0.1.0")
    database: DatabaseReadinessInfo


class ErrorDetail(BaseModel):
    """Structured error payload matching the OpenAPI contract ErrorResponse schema."""

    code: str = Field(..., example="VALIDATION_ERROR")
    message: str = Field(..., example="Request parameters failed validation")
    details: List[Any] = Field(default_factory=list)
    request_id: str = Field(..., example="req_8f1a2b3c")


class ErrorResponse(BaseModel):
    """Standard envelope for error responses across all FoodFlow microservices."""

    error: ErrorDetail

