"""Biometrics calculation endpoints for Profile & Nutrition Service."""

from __future__ import annotations

from fastapi import APIRouter, status

from services.profile_nutrition.calculator import calculate_biometrics
from services.profile_nutrition.schemas import (
    BiometricsCalculationRequest,
    BiometricsCalculationResponse,
)

router = APIRouter(prefix="/api/v1/biometrics", tags=["Biometrics"])


@router.post(
    "/calculate",
    response_model=BiometricsCalculationResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate nutritional and metabolic targets",
    description=(
        "Stateless calculation of Body Mass Index (BMI), Basal Metabolic Rate (BMR via Mifflin-St Jeor), "
        "Total Daily Energy Expenditure (TDEE), and daily caloric/macronutrient goals. "
        "Does not persist user data to disk or database. If sex_for_equation is omitted, returns BMI only."
    ),
)
def calculate_biometrics_endpoint(
    payload: BiometricsCalculationRequest,
) -> BiometricsCalculationResponse:
    """Stateless physical biometrics calculation endpoint."""
    return calculate_biometrics(payload)

