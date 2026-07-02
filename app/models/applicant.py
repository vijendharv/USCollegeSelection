"""Applicant timing and high-school completion context."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from app.models.base import DomainModel


class ApplicantStage(StrEnum):
    JUNIOR = "junior"
    SENIOR = "senior"
    GAP_YEAR = "gap_year"


class HighSchoolContext(DomainModel):
    """Describe which portion of high school is available for evaluation."""

    stage: ApplicantStage | None = None
    graduation_year: int | None = Field(default=None, ge=2020, le=2200)
    academic_record_as_of: date | None = None
