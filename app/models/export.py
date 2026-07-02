"""Generated report-file metadata."""

from __future__ import annotations

from enum import StrEnum

from app.models.base import DomainModel


class ExportFormat(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"


class ExportedFile(DomainModel):
    format: ExportFormat
    filename: str
    path: str
    media_type: str
    size_bytes: int


class ExportResult(DomainModel):
    files: list[ExportedFile]
