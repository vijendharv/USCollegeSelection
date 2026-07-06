"""Completeness assessment without mutating or inventing profile data."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.models.academic import CourseLevel, CourseStatus, GPAType
from app.models.applicant import ApplicantStage
from app.models.base import DomainModel
from app.models.holistic import HolisticReviewStatus
from app.models.student import StudentProfile


class WarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ProfileWarning(DomainModel):
    code: str
    message: str
    path: str
    severity: WarningSeverity


class ProfileAssessment(DomainModel):
    ready_for_analysis: bool
    warnings: list[ProfileWarning] = Field(default_factory=list)


def assess_profile(profile: StudentProfile) -> ProfileAssessment:
    """Describe missing or ambiguous data while preserving the submitted profile."""
    warnings: list[ProfileWarning] = []
    academic = profile.academic
    high_school = profile.high_school
    preferences = profile.preferences

    for index, major in enumerate(preferences.intended_majors):
        if major.strip().casefold() in {"engineering", "business"}:
            warnings.append(
                _warning(
                    "intended_major_too_broad",
                    (
                        f"{major} is too broad for exact six-digit program matching; choose a "
                        "specific field such as Biomedical Engineering, Mechanical Engineering, "
                        "Finance, or Accounting."
                    ),
                    f"preferences.intended_majors.{index}",
                    WarningSeverity.BLOCKING,
                )
            )

    if profile.holistic.review_status is HolisticReviewStatus.NEEDS_REVIEW and (
        profile.holistic.themes or profile.holistic.activities
    ):
        warnings.append(
            _warning(
                "holistic_confirmation_required",
                (
                    "Résumé-derived activities and themes require review and confirmation "
                    "before they can affect fit ranking."
                ),
                "holistic.review_status",
                WarningSeverity.WARNING,
            )
        )

    has_course_grade = any(
        course.grade is not None
        and course.status not in {CourseStatus.IN_PROGRESS, CourseStatus.WITHDRAWN}
        for course in academic.courses
    )
    has_academic_evidence = bool(
        academic.gpas or academic.tests or academic.class_rank or has_course_grade
    )
    if not has_academic_evidence:
        warnings.append(
            _warning(
                "no_academic_evidence",
                "Add a GPA, test score, class rank, or at least one course grade.",
                "academic",
                WarningSeverity.BLOCKING,
            )
        )

    if not academic.courses:
        warnings.append(
            _warning(
                "no_courses",
                "No course-level record is available; rigor and subject preparation are unknown.",
                "academic.courses",
                WarningSeverity.WARNING,
            )
        )

    for index, course in enumerate(academic.courses):
        if course.status is CourseStatus.IN_PROGRESS:
            warnings.append(
                _warning(
                    "course_in_progress",
                    "In-progress course is recorded as rigor but not as a completed grade.",
                    f"academic.courses.{index}",
                    WarningSeverity.INFO,
                )
            )
        elif course.grade is None and course.status is not CourseStatus.WITHDRAWN:
            warnings.append(
                _warning(
                    "course_grade_missing",
                    "Course has no grade yet.",
                    f"academic.courses.{index}.grade",
                    WarningSeverity.WARNING,
                )
            )

        if (
            high_school.stage is ApplicantStage.GAP_YEAR
            and course.status is CourseStatus.IN_PROGRESS
        ):
            warnings.append(
                _warning(
                    "gap_year_in_progress_course",
                    (
                        "A gap-year profile contains an in-progress high-school course; "
                        "confirm its status."
                    ),
                    f"academic.courses.{index}.status",
                    WarningSeverity.WARNING,
                )
            )
        if course.level is CourseLevel.UNKNOWN:
            warnings.append(
                _warning(
                    "course_level_unknown",
                    "Course level is unknown and will not count as advanced rigor.",
                    f"academic.courses.{index}.level",
                    WarningSeverity.INFO,
                )
            )

    for index, gpa in enumerate(academic.gpas):
        if gpa.type is GPAType.UNKNOWN:
            warnings.append(
                _warning(
                    "gpa_type_unknown",
                    "GPA is not identified as weighted or unweighted.",
                    f"academic.gpas.{index}.type",
                    WarningSeverity.WARNING,
                )
            )

    if academic.class_rank is not None and academic.class_size is None:
        warnings.append(
            _warning(
                "class_size_missing",
                "Class size is needed to interpret class rank.",
                "academic.class_size",
                WarningSeverity.WARNING,
            )
        )

    if high_school.stage is None:
        warnings.append(
            _warning(
                "applicant_stage_missing",
                "Select junior, senior, or gap-year applicant stage.",
                "high_school.stage",
                WarningSeverity.BLOCKING,
            )
        )
    if high_school.graduation_year is None:
        warnings.append(
            _warning(
                "graduation_year_missing",
                "High-school graduation year is required.",
                "high_school.graduation_year",
                WarningSeverity.BLOCKING,
            )
        )
    if high_school.academic_record_as_of is None:
        warnings.append(
            _warning(
                "academic_record_date_missing",
                "Record the date through which grades and courses are included.",
                "high_school.academic_record_as_of",
                WarningSeverity.INFO,
            )
        )

    required_preferences = (
        (preferences.residence_state, "residence_state", "State of residence is required."),
        (
            preferences.intended_entry_year,
            "intended_entry_year",
            "Intended entry year is required.",
        ),
        (
            preferences.intended_entry_term,
            "intended_entry_term",
            "Intended entry term is required.",
        ),
    )
    for value, field, message in required_preferences:
        if value is None:
            warnings.append(
                _warning(
                    f"{field}_missing",
                    message,
                    f"preferences.{field}",
                    WarningSeverity.BLOCKING,
                )
            )

    if not preferences.intended_majors:
        warnings.append(
            _warning(
                "intended_majors_missing",
                "At least one intended major or broad field is required.",
                "preferences.intended_majors",
                WarningSeverity.BLOCKING,
            )
        )

    ready = not any(warning.severity is WarningSeverity.BLOCKING for warning in warnings)
    return ProfileAssessment(ready_for_analysis=ready, warnings=warnings)


def _warning(
    code: str,
    message: str,
    path: str,
    severity: WarningSeverity,
) -> ProfileWarning:
    return ProfileWarning(code=code, message=message, path=path, severity=severity)
