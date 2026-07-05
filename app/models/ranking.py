"""Transparent per-major fit-ranking models."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from app.models.base import DomainModel
from app.models.classification import AdmissionCategory
from app.models.preferences import ThresholdMode


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
    national_rank: int | None = Field(default=None, ge=1)
    national_rank_total: int = Field(default=0, ge=0)
    national_program_strength_rank: int | None = Field(default=None, ge=1)
    national_program_strength_rank_total: int = Field(default=0, ge=0)
    applied_fit_threshold: Decimal | None = Field(default=None, ge=0, le=100)
    overall_score: Decimal = Field(ge=0, le=100)
    confidence: FitConfidence
    program_strength_score: Decimal = Field(ge=0, le=100)
    program_strength_confidence: FitConfidence
    methodology_version: str
    cip_codes: list[str] = Field(default_factory=list)
    availability_cip_code: str | None = None
    ranking_cip_code: str | None = None
    match_granularity: int | None = Field(default=None, ge=2, le=6)
    program_offered: bool | None
    components: list[FitComponent]
    missing_inputs: list[str] = Field(default_factory=list)
    explanation: str


class CategoryThresholdResult(DomainModel):
    intended_major: str
    category: AdmissionCategory
    threshold_mode: ThresholdMode
    initial_threshold: Decimal = Field(ge=0, le=100)
    applied_threshold: Decimal = Field(ge=0, le=100)
    adaptive_floor: Decimal = Field(ge=0, le=100)
    minimum_requested: int = Field(ge=1)
    exact_program_candidates: int = Field(ge=0)
    qualified_candidates: int = Field(ge=0)
    selected_candidates: int = Field(ge=0)
    addendum_candidates: int = Field(ge=0)


class ConsolidatedFitResult(DomainModel):
    unit_id: int
    institution_name: str
    rank: int = Field(ge=1)
    score: Decimal = Field(ge=0, le=100)
    supported_majors: list[str]
    explanation: str
