"""Transparent per-major fit-ranking models."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from app.models.base import DomainModel
from app.models.classification import AdmissionCategory


class FitConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FitComponent(DomainModel):
    name: str
    weight: Decimal = Field(ge=0, le=100)
    score: Decimal | None = Field(default=None, ge=0, le=100)
    evidence: str
    missing_inputs: list[str] = Field(default_factory=list)


class MajorFitResult(DomainModel):
    unit_id: int
    institution_name: str
    intended_major: str
    category: AdmissionCategory
    rank: int = Field(ge=1)
    overall_score: Decimal = Field(ge=0, le=100)
    confidence: FitConfidence
    methodology_version: str
    cip_codes: list[str] = Field(default_factory=list)
    program_offered: bool | None
    components: list[FitComponent]
    missing_inputs: list[str] = Field(default_factory=list)
    explanation: str


class ConsolidatedFitResult(DomainModel):
    unit_id: int
    institution_name: str
    rank: int = Field(ge=1)
    score: Decimal = Field(ge=0, le=100)
    supported_majors: list[str]
    explanation: str
