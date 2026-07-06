from decimal import Decimal

from app.academics import analyze_preparation, calculate_gpas
from app.models import Course, CourseLevel, CourseStatus, GPAScope, Grade


def course(name: str, grade: str, level: int, *, advanced: bool = False) -> Course:
    return Course(
        subject=name,
        name=name,
        grade_level=level,
        level=CourseLevel.AP if advanced else CourseLevel.REGULAR,
        grade=Grade(original=grade),
        credits_attempted=Decimal(1),
        status=CourseStatus.COMPLETED,
    )


def test_calculates_core_stem_and_internal_weighted_gpas() -> None:
    results = calculate_gpas(
        [course("Biology", "A", 10, advanced=True), course("English", "B", 11)]
    )
    by_scope = {item.scope: item for item in results}

    assert by_scope[GPAScope.CUMULATIVE].value == Decimal("3.500")
    assert by_scope[GPAScope.STEM].value == Decimal("4.000")
    assert by_scope[GPAScope.INTERNAL_WEIGHTED].value == Decimal("4.000")
    assert by_scope[GPAScope.UC_UNWEIGHTED].value is None


def test_preparation_reports_trend_and_missing_life_science_prerequisites() -> None:
    signals = analyze_preparation(
        [course("Biology", "B", 9), course("Biology", "A", 11, advanced=True)],
        ["Neuroscience"],
    )
    codes = {item.code for item in signals}

    assert "grade_trend" in codes
    assert {"missing_chemistry", "missing_physics", "missing_calculus"} <= codes
