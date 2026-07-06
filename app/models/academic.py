"""Academic records entered manually or extracted from a transcript."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, model_validator

from app.models.base import DomainModel

ShortText = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class RecordSource(StrEnum):
    MANUAL = "manual"
    TRANSCRIPT = "transcript"
    APP_CALCULATED = "app_calculated"


class Term(StrEnum):
    FULL_YEAR = "full_year"
    SEMESTER_1 = "semester_1"
    SEMESTER_2 = "semester_2"
    TRIMESTER_1 = "trimester_1"
    TRIMESTER_2 = "trimester_2"
    TRIMESTER_3 = "trimester_3"
    QUARTER_1 = "quarter_1"
    QUARTER_2 = "quarter_2"
    QUARTER_3 = "quarter_3"
    QUARTER_4 = "quarter_4"
    SUMMER = "summer"
    OTHER = "other"
    UNKNOWN = "unknown"


class CourseLevel(StrEnum):
    REGULAR = "regular"
    HONORS = "honors"
    AP = "ap"
    IB = "ib"
    DUAL_ENROLLMENT = "dual_enrollment"
    OTHER = "other"
    UNKNOWN = "unknown"


class CourseStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    REPEATED = "repeated"
    WITHDRAWN = "withdrawn"
    PASS_FAIL = "pass_fail"
    UNKNOWN = "unknown"


class GPAType(StrEnum):
    WEIGHTED = "weighted"
    UNWEIGHTED = "unweighted"
    UNKNOWN = "unknown"


class GPAScope(StrEnum):
    CUMULATIVE = "cumulative"
    YEAR = "year"
    TERM = "term"
    CORE = "core"
    STEM = "stem"
    TENTH_ELEVENTH = "tenth_eleventh"
    UC_UNWEIGHTED = "uc_unweighted"
    UC_CAPPED_WEIGHTED = "uc_capped_weighted"
    INTERNAL_WEIGHTED = "internal_weighted"
    OTHER = "other"


class StandardizedTest(StrEnum):
    SAT = "sat"
    ACT = "act"
    AP = "ap"
    IB = "ib"


class Grade(DomainModel):
    """Preserve a grade exactly while optionally recording its numeric meaning."""

    original: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    scale: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = None
    numeric_value: Decimal | None = Field(default=None, ge=0)
    maximum_value: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_numeric_pair(self) -> Self:
        if (self.numeric_value is None) != (self.maximum_value is None):
            raise ValueError("numeric_value and maximum_value must be supplied together")
        if (
            self.numeric_value is not None
            and self.maximum_value is not None
            and self.numeric_value > self.maximum_value
        ):
            raise ValueError("numeric_value cannot exceed maximum_value")
        return self


class Course(DomainModel):
    """One repeatable course row from manual entry or a transcript."""

    course_id: UUID = Field(default_factory=uuid4)
    subject: ShortText
    name: ShortText | None = None
    grade_level: int | None = Field(default=None, ge=9, le=12)
    school_year: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    term: Term = Term.UNKNOWN
    level: CourseLevel = CourseLevel.UNKNOWN
    level_original: ShortText | None = None
    grade: Grade | None = None
    credits_attempted: Decimal | None = Field(default=None, ge=0)
    credits_earned: Decimal | None = Field(default=None, ge=0)
    status: CourseStatus = CourseStatus.UNKNOWN
    source: RecordSource = RecordSource.MANUAL
    uc_a_g_area: Annotated[str, StringConstraints(min_length=1, max_length=8)] | None = None
    uc_honors_eligible: bool | None = None

    @model_validator(mode="after")
    def validate_credits(self) -> Self:
        if (
            self.credits_attempted is not None
            and self.credits_earned is not None
            and self.credits_earned > self.credits_attempted
        ):
            raise ValueError("credits_earned cannot exceed credits_attempted")
        return self


class GPARecord(DomainModel):
    """One GPA value; multiple variants remain separate records."""

    value: Decimal = Field(ge=0)
    scale: Decimal = Field(gt=0)
    type: GPAType = GPAType.UNKNOWN
    scope: GPAScope = GPAScope.CUMULATIVE
    source: RecordSource = RecordSource.MANUAL
    school_year: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    term: Term | None = None
    conversion_rule_version: ShortText | None = None

    @model_validator(mode="after")
    def validate_gpa(self) -> Self:
        if self.value > self.scale:
            raise ValueError("GPA value cannot exceed its stated scale")
        if self.source is RecordSource.APP_CALCULATED and not self.conversion_rule_version:
            raise ValueError("app-calculated GPA requires conversion_rule_version")
        return self


class TestScore(DomainModel):
    """A total or section score with test-specific range validation."""

    test: StandardizedTest
    score: Decimal
    section: ShortText | None = None
    test_date: date | None = None

    @model_validator(mode="after")
    def validate_score_range(self) -> Self:
        ranges: dict[StandardizedTest, tuple[Decimal, Decimal]] = {
            StandardizedTest.SAT: (
                (Decimal(200), Decimal(800)) if self.section else (Decimal(400), Decimal(1600))
            ),
            StandardizedTest.ACT: (Decimal(1), Decimal(36)),
            StandardizedTest.AP: (Decimal(1), Decimal(5)),
            StandardizedTest.IB: (Decimal(1), Decimal(7)),
        }
        minimum, maximum = ranges[self.test]
        if not minimum <= self.score <= maximum:
            raise ValueError(
                f"{self.test.value.upper()} score must be between {minimum} and {maximum}"
            )
        return self


class AcademicRecord(DomainModel):
    """A partial academic record that can grow as the user adds information."""

    courses: list[Course] = Field(default_factory=list)
    gpas: list[GPARecord] = Field(default_factory=list)
    tests: list[TestScore] = Field(default_factory=list)
    class_rank: int | None = Field(default=None, ge=1)
    class_size: int | None = Field(default=None, ge=1)
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None

    @model_validator(mode="after")
    def validate_rank(self) -> Self:
        if (
            self.class_rank is not None
            and self.class_size is not None
            and self.class_rank > self.class_size
        ):
            raise ValueError("class_rank cannot exceed class_size")
        return self


class CalculatedGPA(DomainModel):
    scope: GPAScope
    value: Decimal | None = Field(default=None, ge=0)
    scale: Decimal = Field(default=Decimal(4), gt=0)
    courses_used: int = Field(default=0, ge=0)
    caveat: str | None = None


class PreparationSignal(DomainModel):
    code: ShortText
    level: Annotated[str, StringConstraints(pattern="^(strength|attention|unknown)$")]
    message: Annotated[str, StringConstraints(min_length=1, max_length=300)]
