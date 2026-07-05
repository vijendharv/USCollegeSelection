"""Build the canonical college-list and gap-analysis report."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.classification import METHODOLOGY_VERSION, classify_admission
from app.models.academic import CourseLevel
from app.models.classification import AcademicStanding, ClassificationRule
from app.models.college import DatasetVersion, Institution, Ownership
from app.models.preferences import BudgetType
from app.models.report import (
    CollegeReport,
    ComparisonRow,
    GapStatus,
    HolisticContext,
    ReportCandidate,
    SchoolReport,
    SourceReference,
)
from app.models.student import StudentProfile

DISCLAIMER = (
    "Admissions classifications are planning estimates based on available published data, "
    "not guarantees of admission or financial aid. Verify current requirements and costs "
    "with each institution."
)


def build_college_report(
    student: StudentProfile,
    candidates: list[ReportCandidate],
    dataset: DatasetVersion,
    *,
    generated_at: datetime,
    holistic_context: HolisticContext | None = None,
) -> CollegeReport:
    """Build one reproducible model consumed unchanged by every output format."""
    schools = [
        _school_report(student, candidate, dataset)
        for candidate in _deduplicate_candidates(candidates)
    ]
    return CollegeReport(
        generated_at=generated_at,
        methodology_version=METHODOLOGY_VERSION,
        student_profile=student,
        dataset=dataset,
        schools=schools,
        holistic_context=holistic_context
        or HolisticContext(
            themes=student.holistic.themes,
            strengths=[activity.name for activity in student.holistic.activities],
        ),
        disclaimer=DISCLAIMER,
    )


def _school_report(
    student: StudentProfile,
    candidate: ReportCandidate,
    dataset: DatasetVersion,
) -> SchoolReport:
    institution = candidate.institution
    classification = classify_admission(
        student,
        institution,
        dataset,
        candidate.admissions_benchmark,
    )
    sources = _source_references(institution, dataset, candidate)
    comparisons = [
        _academic_comparison(rule, sources)
        for rule in classification.triggered_rules
        if rule.standing is not None
    ]
    comparisons.append(_rigor_comparison(student))
    comparisons.append(_cost_comparison(student, institution, sources[:1]))

    strengths = [row.note for row in comparisons if row.status is GapStatus.STRENGTH and row.note]
    gaps = [row.note for row in comparisons if row.status is GapStatus.GAP and row.note]
    unknowns = list(classification.missing_inputs)
    unknowns.extend(row.note for row in comparisons if row.status is GapStatus.UNKNOWN and row.note)
    if student.preferences.intended_majors:
        unknowns.append("intended-major preparation benchmark is not available")
    warnings = list(classification.excluded_factors)
    warnings.extend(_preference_warnings(student, institution, candidate.user_entered))
    if any(row.status is GapStatus.OVER_BUDGET for row in comparisons):
        warnings.append("Published cost exceeds the stated annual budget.")
    if (
        student.preferences.annual_budget is not None
        and student.preferences.budget_type is BudgetType.NET_PRICE
        and institution.average_net_price is not None
    ):
        warnings.append(
            "Average net price is not a student-specific estimate; use the school's calculator."
        )
    actions = ["Verify current admissions requirements and deadlines with the institution."]
    if gaps:
        actions.append("Review the academic gaps when planning the application strategy.")
    if unknowns:
        actions.append("Verify the missing school benchmarks before making a final decision.")
    if any(row.status is GapStatus.OVER_BUDGET for row in comparisons) or (
        student.preferences.budget_type is BudgetType.NET_PRICE
    ):
        actions.append(
            "Use the institution's official net-price calculator for a personal estimate."
        )

    return SchoolReport(
        institution=institution,
        user_entered=candidate.user_entered,
        classification=classification,
        high_school_gpa_benchmark=_gpa_benchmark_label(candidate),
        comparisons=comparisons,
        strengths=_unique(strengths),
        gaps=_unique(gaps),
        unknowns=_unique(unknowns),
        warnings=_unique(warnings),
        suggested_actions=_unique(actions),
        source_references=sources,
    )


def _gpa_benchmark_label(candidate: ReportCandidate) -> str | None:
    if not candidate.admissions_benchmark.gpas:
        return None
    return "; ".join(
        f"{benchmark.type.value.title()} {benchmark.low}-{benchmark.high}/{benchmark.scale}"
        for benchmark in candidate.admissions_benchmark.gpas
    )


def _academic_comparison(
    rule: ClassificationRule,
    sources: list[SourceReference],
) -> ComparisonRow:
    if rule.standing is None:
        raise ValueError("Academic comparison requires a standing")
    status = {
        AcademicStanding.ABOVE: GapStatus.STRENGTH,
        AcademicStanding.WITHIN: GapStatus.COMPETITIVE,
        AcademicStanding.BELOW: GapStatus.GAP,
    }[rule.standing]
    measure = rule.code.split("_", maxsplit=1)[0].upper()
    return ComparisonRow(
        measure=measure,
        student_value=rule.student_value,
        school_benchmark=rule.school_benchmark,
        gap=rule.numeric_gap,
        status=status,
        sources=sources,
        note=rule.message,
    )


def _rigor_comparison(student: StudentProfile) -> ComparisonRow:
    advanced = {
        CourseLevel.HONORS,
        CourseLevel.AP,
        CourseLevel.IB,
        CourseLevel.DUAL_ENROLLMENT,
    }
    count = sum(course.level in advanced for course in student.academic.courses)
    return ComparisonRow(
        measure="Course rigor",
        student_value=str(count) if count else None,
        school_benchmark=None,
        status=GapStatus.UNKNOWN,
        note="Institution course-rigor benchmark is not available.",
    )


def _cost_comparison(
    student: StudentProfile,
    institution: Institution,
    sources: list[SourceReference],
) -> ComparisonRow:
    budget = student.preferences.annual_budget
    budget_type = student.preferences.budget_type
    if budget is None:
        return ComparisonRow(
            measure="Annual budget",
            status=GapStatus.UNKNOWN,
            sources=sources,
            note="Student annual budget was not provided; cost remains visible but unscored.",
        )

    cost, label = _comparable_cost(student, institution, budget_type)
    if cost is None:
        reason = (
            "No comparable published cost is available."
            if budget_type is not BudgetType.OUT_OF_POCKET
            else "Out-of-pocket budget cannot be compared with average institutional pricing."
        )
        return ComparisonRow(
            measure="Annual budget",
            student_value=_money(budget),
            status=GapStatus.UNKNOWN,
            sources=sources,
            note=reason,
        )

    difference = budget - Decimal(cost)
    within = difference >= 0
    return ComparisonRow(
        measure="Annual budget",
        student_value=_money(budget),
        school_benchmark=f"{_money(Decimal(cost))} {label}",
        gap=difference,
        status=GapStatus.WITHIN_BUDGET if within else GapStatus.OVER_BUDGET,
        sources=sources,
        note=(
            "Published cost is within the stated annual budget."
            if within
            else "Published cost exceeds the stated annual budget."
        ),
    )


def _comparable_cost(
    student: StudentProfile,
    institution: Institution,
    budget_type: BudgetType | None,
) -> tuple[int | None, str]:
    if budget_type is BudgetType.NET_PRICE:
        return institution.average_net_price, "average net price"
    if budget_type is BudgetType.PUBLISHED_COST:
        if institution.cost_of_attendance is not None:
            return institution.cost_of_attendance, "cost of attendance"
        in_state = (
            institution.ownership is Ownership.PUBLIC
            and student.preferences.residence_state == institution.state
        )
        tuition = institution.tuition_in_state if in_state else institution.tuition_out_of_state
        return tuition, "published tuition"
    return None, ""


def _preference_warnings(
    student: StudentProfile,
    institution: Institution,
    user_entered: bool,
) -> list[str]:
    warnings: list[str] = []
    preferences = student.preferences
    if institution.state in preferences.excluded_states:
        warnings.append("School is in a state the student excluded; it remains in the report.")
    if preferences.preferred_states and institution.state not in preferences.preferred_states:
        warnings.append("School is outside the student's preferred states.")
    if user_entered:
        warnings.append("User-entered school retained regardless of matching preferences.")
    return warnings


def _source_references(
    institution: Institution,
    dataset: DatasetVersion,
    candidate: ReportCandidate,
) -> list[SourceReference]:
    sources = [
        SourceReference(
            name=dataset.source_name,
            url=dataset.source_url,
            source_date=dataset.release_date,
        )
    ]
    benchmark = candidate.admissions_benchmark
    if benchmark.source_url or benchmark.source_date:
        sources.append(
            SourceReference(
                name=f"{institution.name} admissions profile",
                url=benchmark.source_url,
                source_date=benchmark.source_date,
            )
        )
    return sources


def _deduplicate_candidates(candidates: list[ReportCandidate]) -> list[ReportCandidate]:
    by_unit_id: dict[int, ReportCandidate] = {}
    for candidate in candidates:
        existing = by_unit_id.get(candidate.institution.unit_id)
        if existing is None or candidate.user_entered:
            by_unit_id[candidate.institution.unit_id] = candidate
    return list(by_unit_id.values())


def _money(value: Decimal) -> str:
    return f"${value:,.0f}"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
