"""Explainable, versioned admissions-classification models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, model_validator

from app.models.academic import GPAType
from app.models.base import DomainModel


class AdmissionCategory(StrEnum):
    SAFETY_LIKELY = "safety_likely"
    TARGET = "target"
    REACH = "reach"
    INSUFFICIENT_DATA = "insufficient_data"


class ClassificationConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AcademicStanding(StrEnum):
    BELOW = "below"
    WITHIN = "within"
    ABOVE = "above"


class GPABenchmark(DomainModel):
    """A school-published GPA range whose type and scale are known."""

    type: GPAType
    scale: Decimal = Field(gt=0)
    low: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> GPABenchmark:
        if self.type is GPAType.UNKNOWN:
            raise ValueError("GPA benchmark type must be weighted or unweighted")
        if self.low > self.high:
            raise ValueError("GPA benchmark low cannot exceed high")
        if self.high > self.scale:
            raise ValueError("GPA benchmark cannot exceed its scale")
        return self


class AdmissionsBenchmark(DomainModel):
    """Optional institution-specific evidence not present in the base college row."""

    gpas: list[GPABenchmark] = Field(default_factory=list)
    source_url: str | None = None
    source_date: date | None = None


class ClassificationRule(DomainModel):
    code: str
    message: str
    standing: AcademicStanding | None = None
    student_value: str | None = None
    school_benchmark: str | None = None
    numeric_gap: Decimal | None = None


class ClassificationResult(DomainModel):
    unit_id: int
    institution_name: str
    category: AdmissionCategory
    confidence: ClassificationConfidence
    methodology_version: str
    triggered_rules: list[ClassificationRule]
    missing_inputs: list[str]
    excluded_factors: list[str]
    source_dates: list[date]
    source_urls: list[str]
    explanation: str
