from __future__ import annotations

from datetime import date

from app.models import (
    AcademicRecord,
    ApplicantStage,
    Course,
    CourseLevel,
    CourseStatus,
    EntryTerm,
    GPARecord,
    GPAType,
    Grade,
    HighSchoolContext,
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


def complete_high_school(
    stage: ApplicantStage = ApplicantStage.SENIOR,
) -> HighSchoolContext:
    return HighSchoolContext(
        stage=stage,
        graduation_year=2027,
        academic_record_as_of=date(2026, 12, 15),
    )


def test_complete_profile_is_ready_without_inventing_optional_values() -> None:
    profile = StudentProfile(
        high_school=complete_high_school(),
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
        high_school=complete_high_school(),
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
        high_school=complete_high_school(),
        academic=AcademicRecord(class_rank=10),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)

    assert assessment.ready_for_analysis is True
    assert "class_size_missing" in {warning.code for warning in assessment.warnings}


def test_junior_profile_is_ready_without_senior_courses() -> None:
    profile = StudentProfile(
        high_school=complete_high_school(ApplicantStage.JUNIOR),
        academic=AcademicRecord(
            courses=[
                Course(
                    subject="English",
                    grade_level=11,
                    grade=Grade(original="A"),
                    status=CourseStatus.COMPLETED,
                )
            ]
        ),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)

    assert assessment.ready_for_analysis is True
    assert not any("senior" in warning.code for warning in assessment.warnings)


def test_senior_in_progress_course_is_not_reported_as_missing_grade() -> None:
    profile = StudentProfile(
        high_school=complete_high_school(ApplicantStage.SENIOR),
        academic=AcademicRecord(
            gpas=[GPARecord(value=3.8, scale=4, type=GPAType.UNWEIGHTED)],
            courses=[
                Course(
                    subject="Mathematics",
                    grade_level=12,
                    level=CourseLevel.AP,
                    status=CourseStatus.IN_PROGRESS,
                )
            ],
        ),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)
    codes = {warning.code for warning in assessment.warnings}

    assert assessment.ready_for_analysis is True
    assert "course_in_progress" in codes
    assert "course_grade_missing" not in codes


def test_gap_year_profile_flags_in_progress_high_school_course() -> None:
    profile = StudentProfile(
        high_school=complete_high_school(ApplicantStage.GAP_YEAR),
        academic=AcademicRecord(
            gpas=[GPARecord(value=3.8, scale=4, type=GPAType.UNWEIGHTED)],
            courses=[
                Course(
                    subject="Science",
                    grade_level=12,
                    status=CourseStatus.IN_PROGRESS,
                )
            ],
        ),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)

    assert "gap_year_in_progress_course" in {warning.code for warning in assessment.warnings}


def test_missing_applicant_stage_and_graduation_year_block_analysis() -> None:
    profile = StudentProfile(
        academic=AcademicRecord(gpas=[GPARecord(value=3.8, scale=4)]),
        preferences=complete_preferences(),
    )

    assessment = assess_profile(profile)
    codes = {warning.code for warning in assessment.warnings}

    assert assessment.ready_for_analysis is False
    assert "applicant_stage_missing" in codes
    assert "graduation_year_missing" in codes
