"""Transparent GPA variants; never substitutes for a school's own recalculation."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.models.academic import (
    CalculatedGPA,
    Course,
    CourseLevel,
    CourseStatus,
    GPAScope,
)

RULE_VERSION = "letter-4.0-v1"
_POINTS = {
    "A+": Decimal("4.0"),
    "A": Decimal("4.0"),
    "A-": Decimal("3.7"),
    "B+": Decimal("3.3"),
    "B": Decimal("3.0"),
    "B-": Decimal("2.7"),
    "C+": Decimal("2.3"),
    "C": Decimal("2.0"),
    "C-": Decimal("1.7"),
    "D+": Decimal("1.3"),
    "D": Decimal("1.0"),
    "D-": Decimal("0.7"),
    "F": Decimal("0"),
}
_CORE = (
    "english",
    "math",
    "algebra",
    "geometry",
    "calculus",
    "biology",
    "chemistry",
    "physics",
    "science",
    "history",
    "social",
    "french",
    "spanish",
    "language",
)
_STEM = (
    "math",
    "algebra",
    "geometry",
    "calculus",
    "biology",
    "chemistry",
    "physics",
    "science",
    "biotech",
    "computer",
    "engineering",
    "physiology",
)


def calculate_gpas(courses: list[Course]) -> list[CalculatedGPA]:
    usable = [course for course in courses if _points(course) is not None]
    results = [
        _calculate(GPAScope.CUMULATIVE, usable),
        _calculate(GPAScope.CORE, [c for c in usable if _matches(c, _CORE)]),
        _calculate(GPAScope.STEM, [c for c in usable if _matches(c, _STEM)]),
        _calculate(GPAScope.TENTH_ELEVENTH, [c for c in usable if c.grade_level in {10, 11}]),
        _calculate(GPAScope.INTERNAL_WEIGHTED, usable, weighted=True),
    ]
    uc = [c for c in usable if c.grade_level in {10, 11} and c.uc_a_g_area]
    if not uc:
        caveat = "Unavailable: UC A-G area and grade-level confirmation were not supplied."
        results.extend(
            [
                CalculatedGPA(scope=GPAScope.UC_UNWEIGHTED, caveat=caveat),
                CalculatedGPA(scope=GPAScope.UC_CAPPED_WEIGHTED, caveat=caveat),
            ]
        )
    else:
        results.append(_calculate(GPAScope.UC_UNWEIGHTED, uc))
        results.append(_calculate(GPAScope.UC_CAPPED_WEIGHTED, uc, uc_weighted=True))
    return results


def _calculate(
    scope: GPAScope, courses: list[Course], *, weighted: bool = False, uc_weighted: bool = False
) -> CalculatedGPA:
    if not courses:
        return CalculatedGPA(
            scope=scope, caveat="Unavailable: no compatible completed letter grades."
        )
    total = Decimal(0)
    credits = Decimal(0)
    honors_credits = Decimal(0)
    for course in courses:
        credit = course.credits_attempted or Decimal(1)
        value = _points(course)
        if value is None or credit <= 0:
            continue
        bonus = Decimal(0)
        if weighted:
            bonus = (
                Decimal("1.0")
                if course.level in {CourseLevel.AP, CourseLevel.IB, CourseLevel.DUAL_ENROLLMENT}
                else Decimal("0.5")
                if course.level is CourseLevel.HONORS
                else Decimal(0)
            )
        if uc_weighted and course.uc_honors_eligible and honors_credits < Decimal(4):
            bonus = min(credit, Decimal(4) - honors_credits) / credit
            honors_credits += min(credit, Decimal(4) - honors_credits)
        total += (value + bonus) * credit
        credits += credit
    value = (total / credits).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    caveat = "App estimate; schools may recalculate differently."
    return CalculatedGPA(
        scope=scope,
        value=value,
        scale=Decimal(5) if weighted else Decimal(4),
        courses_used=len(courses),
        caveat=caveat,
    )


def _points(course: Course) -> Decimal | None:
    if course.status in {CourseStatus.IN_PROGRESS, CourseStatus.WITHDRAWN, CourseStatus.PASS_FAIL}:
        return None
    if course.grade is None:
        return None
    return _POINTS.get(course.grade.original.strip().upper())


def _matches(course: Course, tokens: tuple[str, ...]) -> bool:
    text = f"{course.subject} {course.name or ''}".casefold()
    return any(token in text for token in tokens)
