"""Deterministic admissions classification for first-year applicants."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.academic import (
    CourseLevel,
    GPARecord,
    GPAScope,
    StandardizedTest,
    TestScore,
)
from app.models.classification import (
    AcademicStanding,
    AdmissionCategory,
    AdmissionsBenchmark,
    ClassificationConfidence,
    ClassificationResult,
    ClassificationRule,
    GPABenchmark,
)
from app.models.college import DatasetVersion, Institution
from app.models.preferences import TestSubmissionPlan
from app.models.student import StudentProfile

METHODOLOGY_VERSION = "1.0"
HIGHLY_SELECTIVE_RATE = 0.20
LIKELY_MINIMUM_RATE = 0.50


@dataclass(frozen=True)
class _Signal:
    rule: ClassificationRule
    standing: AcademicStanding


def classify_admission(
    student: StudentProfile,
    institution: Institution,
    dataset: DatasetVersion,
    benchmark: AdmissionsBenchmark | None = None,
) -> ClassificationResult:
    """Classify one institution using only explicit, compatible evidence."""
    benchmark = benchmark or AdmissionsBenchmark()
    rules: list[ClassificationRule] = []
    missing: list[str] = []
    excluded: list[str] = []
    signals: list[_Signal] = []

    _compare_gpa(student, benchmark, signals, missing, excluded)
    _compare_tests(student, institution, signals, missing, excluded)
    _describe_rigor(student, rules, missing)

    rate = institution.acceptance_rate
    if rate is None:
        missing.append("institution acceptance rate")
    elif rate <= HIGHLY_SELECTIVE_RATE:
        rules.append(
            ClassificationRule(
                code="highly_selective_override",
                message="Highly selective institutions remain Reach regardless of academic range.",
                student_value=None,
                school_benchmark=f"acceptance rate {rate:.1%}",
            )
        )

    rules.extend(signal.rule for signal in signals)
    category = _category(rate, signals)
    confidence = _confidence(category, rate, signals, benchmark)
    source_dates = sorted(
        {date for date in (dataset.release_date, benchmark.source_date) if date is not None}
    )
    return ClassificationResult(
        unit_id=institution.unit_id,
        institution_name=institution.name,
        category=category,
        confidence=confidence,
        methodology_version=METHODOLOGY_VERSION,
        triggered_rules=rules,
        missing_inputs=_unique(missing),
        excluded_factors=_unique(excluded),
        source_dates=source_dates,
        source_urls=_unique(
            [url for url in (dataset.source_url, benchmark.source_url) if url is not None]
        ),
        explanation=_explanation(category, confidence, signals, rate),
    )


def _compare_gpa(
    student: StudentProfile,
    benchmark: AdmissionsBenchmark,
    signals: list[_Signal],
    missing: list[str],
    excluded: list[str],
) -> None:
    if not benchmark.gpas:
        missing.append(
            "admitted-student high-school GPA benchmark is not available from the current "
            "official dataset"
        )
        return
    candidates = [gpa for gpa in student.academic.gpas if gpa.scope is GPAScope.CUMULATIVE]
    compatible: list[tuple[GPARecord, GPABenchmark]] = [
        (gpa, school)
        for gpa in candidates
        for school in benchmark.gpas
        if gpa.type is school.type and gpa.scale == school.scale
    ]
    if not compatible:
        if candidates:
            excluded.append("student GPA: incompatible type or scale")
        else:
            missing.append("student cumulative GPA")
        return
    gpa, school = max(compatible, key=lambda pair: pair[0].value)
    standing = _standing(gpa.value, school.low, school.high)
    signals.append(
        _Signal(
            ClassificationRule(
                code=f"gpa_{standing.value}",
                message=f"Compatible {gpa.type.value} GPA is {standing.value} the published range.",
                standing=standing,
                student_value=f"{gpa.value}/{gpa.scale}",
                school_benchmark=f"{school.low}-{school.high}/{school.scale}",
                numeric_gap=_range_gap(gpa.value, school.low, school.high),
            ),
            standing,
        )
    )


def _compare_tests(
    student: StudentProfile,
    institution: Institution,
    signals: list[_Signal],
    missing: list[str],
    excluded: list[str],
) -> None:
    if student.preferences.test_submission_plan is TestSubmissionPlan.DO_NOT_SUBMIT:
        excluded.append("SAT and ACT: student does not plan to submit scores")
        return
    totals = [score for score in student.academic.tests if score.section is None]
    sat = _best_total(totals, StandardizedTest.SAT)
    sat_low = _sum_or_none(institution.sat_reading_25, institution.sat_math_25)
    sat_high = _sum_or_none(institution.sat_reading_75, institution.sat_math_75)
    act = _best_total(totals, StandardizedTest.ACT)
    comparable: list[_Signal] = []

    if sat is not None and sat_low is not None and sat_high is not None:
        comparable.append(_test_signal("sat", sat.score, Decimal(sat_low), Decimal(sat_high)))

    if (
        act is not None
        and institution.act_composite_25 is not None
        and institution.act_composite_75 is not None
    ):
        comparable.append(
            _test_signal(
                "act",
                act.score,
                Decimal(institution.act_composite_25),
                Decimal(institution.act_composite_75),
            )
        )

    if sat is None and act is None:
        missing.append("student SAT or ACT total")
    elif comparable:
        rank = {
            AcademicStanding.BELOW: 0,
            AcademicStanding.WITHIN: 1,
            AcademicStanding.ABOVE: 2,
        }
        signals.append(max(comparable, key=lambda signal: rank[signal.standing]))
        if len(comparable) > 1:
            excluded.append("weaker submitted test comparison")
    else:
        if sat is not None:
            missing.append("institution SAT range")
        if act is not None:
            missing.append("institution ACT range")


def _describe_rigor(
    student: StudentProfile,
    rules: list[ClassificationRule],
    missing: list[str],
) -> None:
    advanced = {
        CourseLevel.HONORS,
        CourseLevel.AP,
        CourseLevel.IB,
        CourseLevel.DUAL_ENROLLMENT,
    }
    count = sum(course.level in advanced for course in student.academic.courses)
    if count:
        rules.append(
            ClassificationRule(
                code="advanced_rigor_observed",
                message="Confirmed advanced courses are reported separately from GPA weighting.",
                student_value=str(count),
                school_benchmark="not available",
            )
        )
    else:
        missing.append("confirmed advanced-course history")


def _category(rate: float | None, signals: list[_Signal]) -> AdmissionCategory:
    if rate is not None and rate <= HIGHLY_SELECTIVE_RATE:
        return AdmissionCategory.REACH
    if not signals:
        return AdmissionCategory.INSUFFICIENT_DATA
    standings = {signal.standing for signal in signals}
    if AcademicStanding.BELOW in standings:
        return AdmissionCategory.REACH
    if rate is not None and rate >= LIKELY_MINIMUM_RATE and standings == {AcademicStanding.ABOVE}:
        return AdmissionCategory.SAFETY_LIKELY
    return AdmissionCategory.TARGET


def _confidence(
    category: AdmissionCategory,
    rate: float | None,
    signals: list[_Signal],
    benchmark: AdmissionsBenchmark,
) -> ClassificationConfidence:
    if category is AdmissionCategory.INSUFFICIENT_DATA:
        return ClassificationConfidence.LOW
    evidence = len(signals) + int(rate is not None)
    if evidence >= 3 and (benchmark.source_date is not None or not benchmark.gpas):
        return ClassificationConfidence.HIGH
    if evidence >= 2:
        return ClassificationConfidence.MEDIUM
    return ClassificationConfidence.LOW


def _test_signal(name: str, value: Decimal, low: Decimal, high: Decimal) -> _Signal:
    standing = _standing(value, low, high)
    return _Signal(
        ClassificationRule(
            code=f"{name}_{standing.value}",
            message=f"{name.upper()} total is {standing.value} the published range.",
            standing=standing,
            student_value=str(value),
            school_benchmark=f"{low}-{high}",
            numeric_gap=_range_gap(value, low, high),
        ),
        standing,
    )


def _standing(value: Decimal, low: Decimal, high: Decimal) -> AcademicStanding:
    if value < low:
        return AcademicStanding.BELOW
    if value > high:
        return AcademicStanding.ABOVE
    return AcademicStanding.WITHIN


def _range_gap(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if value < low:
        return value - low
    if value > high:
        return value - high
    return Decimal(0)


def _best_total(scores: list[TestScore], test: StandardizedTest) -> TestScore | None:
    matches = [score for score in scores if score.test is test]
    return max(matches, key=lambda score: score.score, default=None)


def _sum_or_none(first: int | None, second: int | None) -> int | None:
    return None if first is None or second is None else first + second


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _explanation(
    category: AdmissionCategory,
    confidence: ClassificationConfidence,
    signals: list[_Signal],
    rate: float | None,
) -> str:
    return (
        f"{category.value.replace('_', ' ').title()} with {confidence.value} confidence; "
        f"used {len(signals)} compatible academic comparison(s)"
        + (f" and an overall acceptance rate of {rate:.1%}." if rate is not None else ".")
    )
