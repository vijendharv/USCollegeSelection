from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import (
    AcademicRecord,
    Course,
    CourseLevel,
    CourseStatus,
    GPARecord,
    GPAType,
    Grade,
    RecordSource,
    StandardizedTest,
    Term,
)
from app.models import (
    TestScore as AcademicTestScore,
)


def test_single_partial_course_preserves_only_entered_values() -> None:
    course = Course(subject="Mathematics", grade_level=11, grade=Grade(original="A-"))

    payload = course.model_dump(mode="json", exclude_none=True)

    assert payload["subject"] == "Mathematics"
    assert payload["grade"] == {"original": "A-"}
    assert payload["grade_level"] == 11
    assert "name" not in payload
    assert payload["level"] == "unknown"


def test_multiple_terms_and_advanced_levels_are_preserved() -> None:
    record = AcademicRecord(
        courses=[
            Course(
                subject="English",
                name="Honors English 10",
                school_year="2024-25",
                term=Term.SEMESTER_1,
                level=CourseLevel.HONORS,
                level_original="H",
                grade=Grade(original="A"),
                status=CourseStatus.COMPLETED,
            ),
            Course(
                subject="Computer Science",
                name="AP Computer Science A",
                school_year="2025-26",
                term=Term.FULL_YEAR,
                level=CourseLevel.AP,
                level_original="AP",
                grade=Grade(original="In progress"),
                status=CourseStatus.IN_PROGRESS,
            ),
        ]
    )

    assert [course.level for course in record.courses] == [CourseLevel.HONORS, CourseLevel.AP]
    assert record.courses[0].term is Term.SEMESTER_1
    assert record.courses[1].status is CourseStatus.IN_PROGRESS


def test_weighted_unweighted_unknown_and_calculated_gpas_remain_separate() -> None:
    record = AcademicRecord(
        gpas=[
            GPARecord(value=Decimal("3.80"), scale=4, type=GPAType.UNWEIGHTED),
            GPARecord(value=Decimal("4.35"), scale=5, type=GPAType.WEIGHTED),
            GPARecord(value=Decimal("92"), scale=100, type=GPAType.UNKNOWN),
            GPARecord(
                value=Decimal("3.75"),
                scale=4,
                type=GPAType.UNWEIGHTED,
                source=RecordSource.APP_CALCULATED,
                conversion_rule_version="uscs-1",
            ),
        ]
    )

    assert [gpa.type for gpa in record.gpas] == [
        GPAType.UNWEIGHTED,
        GPAType.WEIGHTED,
        GPAType.UNKNOWN,
        GPAType.UNWEIGHTED,
    ]
    assert record.gpas[-1].source is RecordSource.APP_CALCULATED


def test_app_calculated_gpa_requires_conversion_rule() -> None:
    with pytest.raises(ValidationError, match="conversion_rule_version"):
        GPARecord(value=3.5, scale=4, source=RecordSource.APP_CALCULATED)


def test_earned_credits_cannot_exceed_attempted() -> None:
    with pytest.raises(ValidationError, match="credits_earned"):
        Course(subject="Science", credits_attempted=1, credits_earned=2)


@pytest.mark.parametrize(
    ("test", "score", "section"),
    [
        (StandardizedTest.SAT, 1601, None),
        (StandardizedTest.SAT, 199, "Math"),
        (StandardizedTest.ACT, 37, None),
        (StandardizedTest.AP, 6, "Calculus AB"),
        (StandardizedTest.IB, 8, "English"),
    ],
)
def test_scores_reject_values_outside_published_scales(
    test: StandardizedTest, score: int, section: str | None
) -> None:
    with pytest.raises(ValidationError, match="score must be between"):
        AcademicTestScore(test=test, score=score, section=section)
