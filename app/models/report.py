"""Canonical report models shared by screen, PDF, and spreadsheet outputs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.models.base import DomainModel
from app.models.classification import AdmissionsBenchmark, ClassificationResult
from app.models.college import DatasetVersion, Institution
from app.models.ranking import ConsolidatedFitResult, MajorFitResult
from app.models.student import StudentProfile


class GapStatus(StrEnum):
    STRENGTH = "strength"
    COMPETITIVE = "competitive"
    GAP = "gap"
    WITHIN_BUDGET = "within_budget"
    OVER_BUDGET = "over_budget"
    UNKNOWN = "unknown"


class SourceReference(DomainModel):
    name: str
    url: str | None = None
    source_date: date | None = None


class ComparisonRow(DomainModel):
    measure: str
    student_value: str | None = None
    school_benchmark: str | None = None
    gap: Decimal | None = None
    status: GapStatus
    sources: list[SourceReference] = Field(default_factory=list)
    note: str | None = None


class ReportCandidate(DomainModel):
    institution: Institution
    admissions_benchmark: AdmissionsBenchmark = Field(default_factory=AdmissionsBenchmark)
    user_entered: bool = False


class SchoolReport(DomainModel):
    institution: Institution
    user_entered: bool
    classification: ClassificationResult
    high_school_gpa_benchmark: str | None = None
    comparisons: list[ComparisonRow]
    strengths: list[str]
    gaps: list[str]
    unknowns: list[str]
    warnings: list[str]
    suggested_actions: list[str]
    source_references: list[SourceReference]


class HolisticContext(DomainModel):
    """Confirmed résumé/activity context; never changes the numeric classification."""

    themes: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)


class CollegeReport(DomainModel):
    report_version: Literal["1.1"] = "1.1"
    generated_at: datetime
    methodology_version: str
    student_profile: StudentProfile
    dataset: DatasetVersion
    schools: list[SchoolReport]
    student_supplied_rankings: list[MajorFitResult] = Field(default_factory=list)
    major_rankings: list[MajorFitResult] = Field(default_factory=list)
    addendum_rankings: list[MajorFitResult] = Field(default_factory=list)
    consolidated_rankings: list[ConsolidatedFitResult] = Field(default_factory=list)
    fit_methodology_version: str | None = None
    holistic_context: HolisticContext = Field(default_factory=HolisticContext)
    disclaimer: str
