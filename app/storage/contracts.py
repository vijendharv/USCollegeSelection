"""Storage contracts used by application services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.models import DatasetVersion, Institution, InstitutionFilters


class StorageError(RuntimeError):
    """A stable application error for storage operations."""


class CollegeStore(Protocol):
    """Boundary for public college data."""

    def healthcheck(self) -> bool: ...

    def get_institution(self, unit_id: int) -> Institution | None: ...

    def search_institutions(self, filters: InstitutionFilters) -> list[Institution]: ...

    def current_dataset_version(self) -> DatasetVersion | None: ...

    def close(self) -> None: ...


class SessionFileStore(Protocol):
    """Boundary for temporary private uploads and generated reports."""

    def create_session(self) -> tuple[str, Path]: ...

    def session_path(self, session_id: str) -> Path: ...

    def delete_session(self, session_id: str) -> None: ...
