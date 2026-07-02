from __future__ import annotations

from app.models import (
    AcademicRecord,
    Course,
    CourseLevel,
    EntryTerm,
    GPARecord,
    GPAType,
    Grade,
    StudentPreferences,
    StudentProfile,
    WarningSeverity,
    assess_profile,
)


def complete_preferences() -> StudentPreferences:
    return StudentPreferences(
        residence_state="CA",
        intended_entry_year=2027,
        intended_entry_term=EntryTerm.FALL,
        intended_majors=["Computer Science"],
    )


def test_complete_profile_is_ready_without_inventing_optional_values() -> None:
    profile = StudentProfile(
        academic=AcademicRecord(
            courses=[
                Course(
                    subject="Mathematics",
                    name="AP Calculus AB",
                    level=CourseLevel.AP,
                    grade=Grade(original="A"),
                )
            ]
        ),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)
    serialized = profile.model_dump(mode="json", exclude_none=True)

    assert assessment.ready_for_analysis is True
    assert assessment.warnings == []
    assert serialized["academic"]["gpas"] == []
    assert serialized["academic"]["tests"] == []


def test_empty_partial_profile_returns_blocking_warnings() -> None:
    assessment = assess_profile(StudentProfile())

    codes = {warning.code for warning in assessment.warnings}
    assert assessment.ready_for_analysis is False
    assert "no_academic_evidence" in codes
    assert "residence_state_missing" in codes
    assert "intended_entry_year_missing" in codes
    assert "intended_entry_term_missing" in codes
    assert "intended_majors_missing" in codes


def test_missing_course_fields_and_unknown_gpa_are_warnings_not_errors() -> None:
    profile = StudentProfile(
        academic=AcademicRecord(
            courses=[Course(subject="History")],
            gpas=[GPARecord(value=3.7, scale=4, type=GPAType.UNKNOWN)],
        ),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)
    warnings = {warning.code: warning for warning in assessment.warnings}

    assert assessment.ready_for_analysis is True
    assert warnings["course_grade_missing"].severity is WarningSeverity.WARNING
    assert warnings["course_level_unknown"].severity is WarningSeverity.INFO
    assert warnings["gpa_type_unknown"].severity is WarningSeverity.WARNING


def test_class_rank_without_size_is_reported() -> None:
    profile = StudentProfile(
        academic=AcademicRecord(class_rank=10),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)

    assert assessment.ready_for_analysis is True
    assert "class_size_missing" in {warning.code for warning in assessment.warnings}
