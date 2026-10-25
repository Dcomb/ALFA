# backend/app/schemas.py

from typing import Any, Literal
from pydantic import BaseModel, Field


class CreditApplication(BaseModel):
    application_id: str | None = None

    business_type: str | None = None
    business_age_months: int | None = Field(default=None, ge=0)
    monthly_revenue: float | None = Field(default=None, ge=0)

    credit_purpose: str | None = None
    requested_amount: float | None = Field(default=None, gt=0)
    requested_term_months: int | None = Field(default=None, gt=0)

    status: Literal[
        "collecting",
        "ready_for_recommendation",
        "offers_ready",
        "draft",
        "submitted",
    ] = "collecting"


class RecommendedProduct(BaseModel):
    product_id: str
    name: str
    score: float | None = None
    explanation: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1, max_length=64)


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    application: CreditApplication | None = None
    recommendations: list[RecommendedProduct] = Field(default_factory=list)