"""Top-level student profile."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from app.models.academic import AcademicRecord
from app.models.base import DomainModel
from app.models.preferences import StudentPreferences


class StudentProfile(DomainModel):
    """Canonical, incrementally editable student profile."""

    schema_version: Literal["1.0"] = "1.0"
    profile_id: UUID = Field(default_factory=uuid4)
    academic: AcademicRecord = Field(default_factory=AcademicRecord)
    preferences: StudentPreferences = Field(default_factory=StudentPreferences)
