from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.models import (
    AcademicRecord,
    AdmissionCategory,
    AdmissionsBenchmark,
    BudgetType,
    CollegeReport,
    Course,
    CourseLevel,
    DatasetVersion,
    GapStatus,
    GPABenchmark,
    GPARecord,
    GPAType,
    HolisticContext,
    Institution,
    Ownership,
    ReportCandidate,
    StudentPreferences,
    StudentProfile,
)
from app.models import (
    TestScore as StudentTestScore,
)
from app.models.academic import StandardizedTest
from app.reporting import DISCLAIMER, build_college_report

GENERATED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def dataset() -> DatasetVersion:
    return DatasetVersion(
        version_id="scorecard-fixture",
        source_name="College Scorecard",
        source_url="https://example.edu/scorecard.zip",
        archive_member="institutions.csv",
        release_date=date(2026, 6, 10),
        retrieved_at=datetime(2026, 7, 1, tzinfo=UTC),
        sha256="a" * 64,
        raw_row_count=10,
        eligible_row_count=4,
        schema_version=1,
    )


def student(
    *,
    sat: int | None = 1350,
    budget: int | None = 30_000,
    budget_type: BudgetType = BudgetType.PUBLISHED_COST,
) -> StudentProfile:
    tests = (
        [StudentTestScore(test=StandardizedTest.SAT, score=Decimal(sat))] if sat is not None else []
    )
    return StudentProfile(
        profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        academic=AcademicRecord(
            gpas=[GPARecord(value=Decimal("3.7"), scale=Decimal("4"), type=GPAType.UNWEIGHTED)],
            tests=tests,
            courses=[Course(subject="Mathematics", name="AP Calculus", level=CourseLevel.AP)],
        ),
        preferences=StudentPreferences(
            residence_state="CA",
            intended_majors=["Computer Science"],
            annual_budget=Decimal(budget) if budget is not None else None,
            budget_type=budget_type if budget is not None else None,
            preferred_states=["CA"],
            excluded_states=["TX"],
            existing_schools=["Reach University"],
        ),
    )


def school(
    unit_id: int,
    name: str,
    *,
    state: str = "CA",
    rate: float | None = 0.60,
    sat_low: int | None = 1200,
    sat_high: int | None = 1400,
    cost: int | None = 28_000,
) -> Institution:
    reading_low = sat_low // 2 if sat_low is not None else None
    math_low = sat_low - reading_low if sat_low is not None and reading_low is not None else None
    reading_high = sat_high // 2 if sat_high is not None else None
    math_high = (
        sat_high - reading_high if sat_high is not None and reading_high is not None else None
    )
    return Institution(
        unit_id=unit_id,
        name=name,
        city="Example",
        state=state,
        ownership=Ownership.PRIVATE_NONPROFIT,
        main_campus=True,
        highest_degree=3,
        acceptance_rate=rate,
        sat_reading_25=reading_low,
        sat_math_25=math_low,
        sat_reading_75=reading_high,
        sat_math_75=math_high,
        cost_of_attendance=cost,
        average_net_price=cost,
        dataset_version_id="scorecard-fixture",
    )


def benchmark() -> AdmissionsBenchmark:
    return AdmissionsBenchmark(
        gpas=[
            GPABenchmark(
                type=GPAType.UNWEIGHTED,
                scale=Decimal("4"),
                low=Decimal("3.5"),
                high=Decimal("3.9"),
            )
        ],
        source_url="https://example.edu/admissions",
        source_date=date(2026, 5, 1),
    )


def sample_report() -> CollegeReport:
    candidates = [
        ReportCandidate(
            institution=school(1, "Likely University", sat_low=1100, sat_high=1300),
        ),
        ReportCandidate(
            institution=school(2, "Target University"), admissions_benchmark=benchmark()
        ),
        ReportCandidate(
            institution=school(3, "Reach University", rate=0.10),
            admissions_benchmark=benchmark(),
            user_entered=True,
        ),
        ReportCandidate(
            institution=school(4, "Unknown University", rate=0.70, sat_low=None, sat_high=None)
        ),
    ]
    return build_college_report(student(), candidates, dataset(), generated_at=GENERATED_AT)


def test_report_contains_all_categories_and_reproducible_metadata() -> None:
    report = sample_report()

    assert {item.classification.category for item in report.schools} == set(AdmissionCategory)
    assert report.generated_at == GENERATED_AT
    assert report.report_version == "1.0"
    assert report.methodology_version == "1.0"
    assert report.disclaimer == DISCLAIMER
    snapshot = {
        "report_version": report.report_version,
        "generated_at": report.generated_at.isoformat(),
        "methodology_version": report.methodology_version,
        "dataset_version": report.dataset.version_id,
        "schools": [
            {
                "unit_id": item.institution.unit_id,
                "name": item.institution.name,
                "category": item.classification.category.value,
                "user_entered": item.user_entered,
            }
            for item in report.schools
        ],
    }
    expected = json.loads(
        Path("tests/fixtures/report/category-matrix.json").read_text(encoding="utf-8")
    )
    assert snapshot == expected


def test_academic_rows_include_numeric_gap_status_and_sources() -> None:
    report = build_college_report(
        student(sat=1100),
        [
            ReportCandidate(
                institution=school(1, "Reach University"), admissions_benchmark=benchmark()
            )
        ],
        dataset(),
        generated_at=GENERATED_AT,
    )

    sat = next(row for row in report.schools[0].comparisons if row.measure == "SAT")
    assert sat.gap == Decimal("-100")
    assert sat.status is GapStatus.GAP
    assert len(sat.sources) == 2
    assert report.schools[0].gaps == ["SAT total is below the published range."]


def test_budget_comparison_uses_declared_budget_meaning() -> None:
    report = build_college_report(
        student(budget=30_000),
        [ReportCandidate(institution=school(1, "Affordable University", cost=28_000))],
        dataset(),
        generated_at=GENERATED_AT,
    )

    cost = next(row for row in report.schools[0].comparisons if row.measure == "Annual budget")
    assert cost.status is GapStatus.WITHIN_BUDGET
    assert cost.gap == Decimal("2000")
    assert cost.school_benchmark == "$28,000 cost of attendance"


def test_over_budget_creates_warning_without_changing_classification() -> None:
    report = build_college_report(
        student(budget=20_000),
        [ReportCandidate(institution=school(1, "Expensive University", cost=50_000))],
        dataset(),
        generated_at=GENERATED_AT,
    )
    item = report.schools[0]

    assert item.classification.category is AdmissionCategory.TARGET
    assert "Published cost exceeds the stated annual budget." in item.warnings
    assert (
        "Use the institution's official net-price calculator for a personal estimate."
        in item.suggested_actions
    )


def test_missing_budget_is_visible_but_not_penalized() -> None:
    report = build_college_report(
        student(budget=None),
        [ReportCandidate(institution=school(1, "Example University"))],
        dataset(),
        generated_at=GENERATED_AT,
    )
    cost = next(row for row in report.schools[0].comparisons if row.measure == "Annual budget")

    assert cost.status is GapStatus.UNKNOWN
    assert "cost remains visible but unscored" in (cost.note or "")


def test_out_of_pocket_budget_is_not_compared_to_average_price() -> None:
    report = build_college_report(
        student(budget_type=BudgetType.OUT_OF_POCKET),
        [ReportCandidate(institution=school(1, "Example University"))],
        dataset(),
        generated_at=GENERATED_AT,
    )
    cost = next(row for row in report.schools[0].comparisons if row.measure == "Annual budget")

    assert cost.status is GapStatus.UNKNOWN
    assert "cannot be compared" in (cost.note or "")


def test_net_price_budget_uses_average_with_personalization_warning() -> None:
    report = build_college_report(
        student(budget_type=BudgetType.NET_PRICE),
        [ReportCandidate(institution=school(1, "Example University", cost=28_000))],
        dataset(),
        generated_at=GENERATED_AT,
    )
    item = report.schools[0]
    cost = next(row for row in item.comparisons if row.measure == "Annual budget")

    assert cost.school_benchmark == "$28,000 average net price"
    assert any(
        "Average net price is not a student-specific estimate" in warning
        for warning in item.warnings
    )


def test_published_cost_falls_back_to_public_in_state_tuition() -> None:
    institution = school(1, "Public University", cost=None)
    institution.ownership = Ownership.PUBLIC
    institution.tuition_in_state = 12_000
    institution.tuition_out_of_state = 35_000
    report = build_college_report(
        student(),
        [ReportCandidate(institution=institution)],
        dataset(),
        generated_at=GENERATED_AT,
    )
    cost = next(row for row in report.schools[0].comparisons if row.measure == "Annual budget")

    assert cost.school_benchmark == "$12,000 published tuition"
    assert cost.status is GapStatus.WITHIN_BUDGET


def test_user_entered_school_is_retained_despite_excluded_state() -> None:
    entered = ReportCandidate(
        institution=school(1, "Reach University", state="TX"),
        user_entered=True,
    )
    duplicate_match = ReportCandidate(institution=school(1, "Reach University", state="TX"))

    report = build_college_report(
        student(), [duplicate_match, entered], dataset(), generated_at=GENERATED_AT
    )

    assert len(report.schools) == 1
    assert report.schools[0].user_entered
    assert (
        "School is in a state the student excluded; it remains in the report."
        in report.schools[0].warnings
    )
    assert (
        "User-entered school retained regardless of matching preferences."
        in report.schools[0].warnings
    )


def test_missing_and_excluded_classification_data_remain_distinct() -> None:
    mismatched = AdmissionsBenchmark(
        gpas=[
            GPABenchmark(
                type=GPAType.WEIGHTED,
                scale=Decimal("5"),
                low=Decimal("4"),
                high=Decimal("4.8"),
            )
        ]
    )
    report = build_college_report(
        student(sat=None),
        [
            ReportCandidate(
                institution=school(1, "Unknown University"), admissions_benchmark=mismatched
            )
        ],
        dataset(),
        generated_at=GENERATED_AT,
    )
    item = report.schools[0]

    assert "student SAT or ACT total" in item.unknowns
    assert "student GPA: incompatible type or scale" in item.warnings


def test_confirmed_holistic_context_is_preserved_without_changing_category() -> None:
    context = HolisticContext(
        themes=["Robotics"],
        strengths=["Sustained team leadership"],
        opportunities=["Quantify project impact"],
    )
    report = build_college_report(
        student(),
        [ReportCandidate(institution=school(1, "Example University"))],
        dataset(),
        generated_at=GENERATED_AT,
        holistic_context=context,
    )

    assert report.holistic_context == context
    assert report.schools[0].classification.category is AdmissionCategory.TARGET
    assert "intended-major preparation benchmark is not available" in report.schools[0].unknowns
