from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.classification import METHODOLOGY_VERSION, classify_admission
from app.models import (
    AcademicRecord,
    AdmissionCategory,
    AdmissionsBenchmark,
    ClassificationConfidence,
    Course,
    CourseLevel,
    DatasetVersion,
    GPABenchmark,
    GPARecord,
    GPAType,
    Institution,
    Ownership,
    ResidencySelectivity,
    StudentPreferences,
    StudentProfile,
)
from app.models import (
    TestPolicy as InstitutionTestPolicy,
)
from app.models import (
    TestScore as StudentTestScore,
)
from app.models import (
    TestSubmissionPlan as SubmissionPlan,
)
from app.models.academic import StandardizedTest


def institution(*, acceptance_rate: float | None = 0.60) -> Institution:
    return Institution(
        unit_id=1,
        name="Example University",
        city="Example",
        state="CA",
        main_campus=True,
        highest_degree=3,
        acceptance_rate=acceptance_rate,
        sat_reading_25=600,
        sat_reading_75=700,
        sat_math_25=600,
        sat_math_75=700,
        act_composite_25=27,
        act_composite_75=32,
        dataset_version_id="scorecard-test",
    )


def dataset() -> DatasetVersion:
    return DatasetVersion(
        version_id="scorecard-test",
        source_name="College Scorecard",
        source_url="https://example.edu/data.zip",
        archive_member="institutions.csv",
        release_date=date(2026, 6, 10),
        retrieved_at=datetime(2026, 7, 1, tzinfo=UTC),
        sha256="a" * 64,
        raw_row_count=10,
        eligible_row_count=8,
        schema_version=1,
    )


def profile(
    *,
    sat: int | None = None,
    act: int | None = None,
    gpa: tuple[str, str, GPAType] | None = None,
    advanced_courses: int = 0,
    submission: SubmissionPlan = SubmissionPlan.SUBMIT,
) -> StudentProfile:
    gpas = [GPARecord(value=Decimal(gpa[0]), scale=Decimal(gpa[1]), type=gpa[2])] if gpa else []
    tests = []
    if sat is not None:
        tests.append(StudentTestScore(test=StandardizedTest.SAT, score=Decimal(sat)))
    if act is not None:
        tests.append(StudentTestScore(test=StandardizedTest.ACT, score=Decimal(act)))
    courses = [
        Course(subject="Mathematics", name=f"AP Course {index}", level=CourseLevel.AP)
        for index in range(advanced_courses)
    ]
    return StudentProfile(
        academic=AcademicRecord(gpas=gpas, tests=tests, courses=courses),
        preferences=StudentPreferences(test_submission_plan=submission),
    )


def gpa_benchmark(
    *,
    kind: GPAType = GPAType.UNWEIGHTED,
    scale: str = "4.0",
) -> AdmissionsBenchmark:
    return AdmissionsBenchmark(
        gpas=[
            GPABenchmark(
                type=kind,
                scale=Decimal(scale),
                low=Decimal("3.4"),
                high=Decimal("3.8"),
            )
        ],
        source_url="https://example.edu/admissions",
        source_date=date(2026, 5, 1),
    )


@pytest.mark.parametrize(
    ("rate", "sat", "expected"),
    [
        (0.50, 1410, AdmissionCategory.SAFETY_LIKELY),
        (0.499, 1410, AdmissionCategory.TARGET),
        (0.60, 1400, AdmissionCategory.TARGET),
        (0.60, 1200, AdmissionCategory.TARGET),
        (0.60, 1190, AdmissionCategory.REACH),
        (0.20, 1500, AdmissionCategory.REACH),
    ],
)
def test_versioned_category_boundaries(
    rate: float,
    sat: int,
    expected: AdmissionCategory,
) -> None:
    result = classify_admission(profile(sat=sat), institution(acceptance_rate=rate), dataset())

    assert result.category is expected
    assert result.methodology_version == METHODOLOGY_VERSION


def test_highly_selective_override_applies_without_academic_benchmarks() -> None:
    result = classify_admission(profile(), institution(acceptance_rate=0.10), dataset())

    assert result.category is AdmissionCategory.REACH
    assert result.confidence is ClassificationConfidence.LOW
    assert "highly_selective_override" in {rule.code for rule in result.triggered_rules}


def test_missing_benchmarks_returns_insufficient_data() -> None:
    school = institution(acceptance_rate=0.60)
    school.sat_reading_25 = None
    result = classify_admission(profile(sat=1300), school, dataset())

    assert result.category is AdmissionCategory.INSUFFICIENT_DATA
    assert "institution SAT range" in result.missing_inputs


def test_only_compatible_gpa_type_and_scale_are_compared() -> None:
    incompatible = classify_admission(
        profile(gpa=("3.9", "5.0", GPAType.WEIGHTED)),
        institution(),
        dataset(),
        gpa_benchmark(),
    )
    compatible = classify_admission(
        profile(gpa=("3.9", "4.0", GPAType.UNWEIGHTED)),
        institution(),
        dataset(),
        gpa_benchmark(),
    )

    assert incompatible.category is AdmissionCategory.INSUFFICIENT_DATA
    assert "student GPA: incompatible type or scale" in incompatible.excluded_factors
    assert compatible.category is AdmissionCategory.SAFETY_LIKELY
    assert "gpa_above" in {rule.code for rule in compatible.triggered_rules}


def test_course_rigor_is_reported_separately_from_gpa() -> None:
    result = classify_admission(profile(sat=1300, advanced_courses=2), institution(), dataset())

    rigor = next(rule for rule in result.triggered_rules if rule.code == "advanced_rigor_observed")
    assert rigor.student_value == "2"
    assert result.category is AdmissionCategory.TARGET


def test_act_alone_supports_classification() -> None:
    result = classify_admission(profile(act=33), institution(), dataset())

    assert result.category is AdmissionCategory.SAFETY_LIKELY
    assert "act_above" in {rule.code for rule in result.triggered_rules}
    assert "provisional_likely_test_only" in {rule.code for rule in result.triggered_rules}


def test_stronger_of_sat_and_act_is_used() -> None:
    result = classify_admission(profile(sat=1100, act=33), institution(), dataset())

    assert result.category is AdmissionCategory.SAFETY_LIKELY
    assert "act_above" in {rule.code for rule in result.triggered_rules}
    assert "sat_below" not in {rule.code for rule in result.triggered_rules}
    assert "weaker submitted test comparison" in result.excluded_factors


def test_do_not_submit_excludes_scores_from_classification() -> None:
    result = classify_admission(
        profile(sat=1500, submission=SubmissionPlan.DO_NOT_SUBMIT),
        institution(),
        dataset(),
    )

    assert result.category is AdmissionCategory.INSUFFICIENT_DATA
    assert "SAT and ACT: student does not plan to submit scores" in result.excluded_factors


def test_result_exposes_sources_rules_missing_inputs_and_confidence() -> None:
    result = classify_admission(
        profile(sat=1450, gpa=("3.9", "4.0", GPAType.UNWEIGHTED)),
        institution(),
        dataset(),
        gpa_benchmark(),
    )

    assert result.category is AdmissionCategory.SAFETY_LIKELY
    assert result.confidence is ClassificationConfidence.HIGH
    assert result.source_dates == [date(2026, 5, 1), date(2026, 6, 10)]
    assert result.source_urls == [
        "https://example.edu/data.zip",
        "https://example.edu/admissions",
    ]
    assert {rule.code for rule in result.triggered_rules} >= {"gpa_above", "sat_above"}


def test_test_blind_school_excludes_scores() -> None:
    school = institution()
    school.test_policy = InstitutionTestPolicy.BLIND
    result = classify_admission(profile(sat=1500), school, dataset())

    assert result.category is AdmissionCategory.INSUFFICIENT_DATA
    assert any("does not use" in value for value in result.excluded_factors)


def test_broad_access_school_can_be_provisional_likely_without_test_range() -> None:
    school = institution(acceptance_rate=0.80)
    school.sat_reading_25 = None
    school.sat_reading_75 = None
    school.sat_math_25 = None
    school.sat_math_75 = None
    school.act_composite_25 = None
    school.act_composite_75 = None
    result = classify_admission(profile(gpa=("3.6", "4.0", GPAType.UNWEIGHTED)), school, dataset())

    assert result.category is AdmissionCategory.SAFETY_LIKELY
    assert result.confidence is ClassificationConfidence.LOW
    assert "provisional_likely_broad_access" in {rule.code for rule in result.triggered_rules}


def test_test_blind_school_does_not_use_broad_access_fallback() -> None:
    school = institution(acceptance_rate=0.90)
    school.test_policy = InstitutionTestPolicy.BLIND
    result = classify_admission(profile(gpa=("3.9", "4.0", GPAType.UNWEIGHTED)), school, dataset())

    assert result.category is AdmissionCategory.INSUFFICIENT_DATA


def test_high_oos_selectivity_downgrades_public_school_once() -> None:
    school = institution()
    school.ownership = Ownership.PUBLIC
    school.state = "NC"
    school.residency_selectivity = ResidencySelectivity.HIGH
    applicant = profile(
        sat=1450,
        gpa=("3.9", "4.0", GPAType.UNWEIGHTED),
    )
    applicant.preferences.residence_state = "WA"
    result = classify_admission(applicant, school, dataset(), gpa_benchmark())

    assert result.category is AdmissionCategory.TARGET
    assert "out_of_state_public_adjustment" in {rule.code for rule in result.triggered_rules}


def test_gpa_benchmark_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="type must be weighted or unweighted"):
        GPABenchmark(
            type=GPAType.UNKNOWN,
            scale=Decimal("4"),
            low=Decimal("3"),
            high=Decimal("4"),
        )
