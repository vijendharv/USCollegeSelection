"""Typed domain models for student academics and preferences."""

from app.models.academic import (
    AcademicRecord,
    Course,
    CourseLevel,
    CourseStatus,
    GPARecord,
    GPAScope,
    GPAType,
    Grade,
    RecordSource,
    StandardizedTest,
    Term,
    TestScore,
)
from app.models.assessment import (
    ProfileAssessment,
    ProfileWarning,
    WarningSeverity,
    assess_profile,
)
from app.models.preferences import (
    BudgetType,
    EntryTerm,
    StudentPreferences,
    TestSubmissionPlan,
)
from app.models.student import StudentProfile

__all__ = [
    "AcademicRecord",
    "BudgetType",
    "Course",
    "CourseLevel",
    "CourseStatus",
    "EntryTerm",
    "GPARecord",
    "GPAScope",
    "GPAType",
    "Grade",
    "ProfileAssessment",
    "ProfileWarning",
    "RecordSource",
    "StandardizedTest",
    "StudentPreferences",
    "StudentProfile",
    "Term",
    "TestScore",
    "TestSubmissionPlan",
    "WarningSeverity",
    "assess_profile",
]
