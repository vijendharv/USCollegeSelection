"""Offline end-to-end demo orchestration using only frozen public fixture data."""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from app.exporting import export_college_report
from app.models import (
    AdmissionCategory,
    ExportFormat,
    Institution,
    InstitutionFilters,
    ReportCandidate,
    SchoolReport,
    StudentProfile,
    assess_profile,
)
from app.reporting import build_college_report
from app.storage import DuckDBCollegeStore, LocalSessionFileStore, StorageError

_FIXTURE_SOURCE_URL = "https://collegescorecard.ed.gov/data/"
_FIXTURE_RELEASE_DATE = date(2026, 6, 10)
_ARCHIVE_MEMBER = "Most-Recent-Cohorts-Institution.csv"


class DemoError(RuntimeError):
    """A user-actionable offline demo failure."""


def run_offline_demo(
    *,
    profile_path: Path,
    database_path: Path,
    output_root: Path,
    fixture_csv_path: Path | None = None,
    schools_per_category: int = 10,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Analyze a real local DuckDB database and export a balanced local report."""
    if not 1 <= schools_per_category <= 10:
        raise DemoError("schools_per_category must be between 1 and 10")
    profile = _load_profile(profile_path)
    assessment = assess_profile(profile)
    if not assessment.ready_for_analysis:
        blocking = [
            warning.code for warning in assessment.warnings if warning.severity.value == "blocking"
        ]
        raise DemoError(f"Student profile is not ready for analysis: {', '.join(blocking)}")
    built_database = not _database_is_healthy(database_path)
    if built_database:
        if fixture_csv_path is None:
            raise DemoError(
                f"Real college database not found: {database_path}. "
                "Run `uv run python -m app refresh-data` first."
            )
        if not fixture_csv_path.is_file():
            raise DemoError(f"College fixture not found: {fixture_csv_path}")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path = database_path.parent / "demo-scorecard.zip"
        _build_fixture_archive(fixture_csv_path, archive_path)
        with DuckDBCollegeStore(database_path, read_only=False) as store:
            store.refresh_from_scorecard_zip(
                archive_path,
                source_url=_FIXTURE_SOURCE_URL,
                retrieved_at=generated_at or datetime.now(UTC),
                release_date=_FIXTURE_RELEASE_DATE,
                minimum_eligible_institutions=1,
            )

    with DuckDBCollegeStore(database_path) as college_store:
        institutions = _load_all_institutions(college_store)
        dataset = college_store.current_dataset_version()
    if dataset is None or not institutions:
        raise DemoError("Demo college database contains no usable institutions")

    existing = {name.casefold() for name in profile.preferences.existing_schools}
    preferred_states = set(profile.preferences.preferred_states)
    candidates = [
        ReportCandidate(
            institution=institution,
            user_entered=institution.name.casefold() in existing,
        )
        for institution in institutions
        if not preferred_states
        or institution.state in preferred_states
        or institution.name.casefold() in existing
    ]
    complete_report = build_college_report(
        profile,
        candidates,
        dataset,
        generated_at=generated_at or datetime.now(UTC),
    )
    report = complete_report.model_copy(
        update={
            "schools": _balanced_school_list(
                complete_report.schools,
                schools_per_category=schools_per_category,
            )
        }
    )

    file_store = LocalSessionFileStore(output_root)
    session_id, output_directory = file_store.create_session()
    exports = export_college_report(
        report,
        file_store,
        session_id,
        {ExportFormat.PDF, ExportFormat.XLSX},
        filename_stem="college-report",
    )
    report_path = file_store.write_file(
        session_id,
        "college-report.json",
        report.model_dump_json(indent=2).encode("utf-8"),
    )
    counts = Counter(item.classification.category.value for item in report.schools)
    return {
        "status": "ok",
        "offline": True,
        "profile_path": str(profile_path),
        "database_path": str(database_path),
        "database_built": built_database,
        "database_institutions": len(institutions),
        "matching_institutions": len(complete_report.schools),
        "reported_schools": len(report.schools),
        "category_counts": dict(sorted(counts.items())),
        "output_directory": str(output_directory),
        "files": [file.path for file in exports.files] + [str(report_path)],
    }


def _load_profile(path: Path) -> StudentProfile:
    if not path.is_file():
        raise DemoError(f"Student profile not found: {path}")
    try:
        return StudentProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise DemoError(f"Student profile is invalid: {path}") from exc


def _database_is_healthy(path: Path) -> bool:
    with DuckDBCollegeStore(path) as store:
        return store.healthcheck()


def _load_all_institutions(store: DuckDBCollegeStore) -> list[Institution]:
    institutions: list[Institution] = []
    offset = 0
    while True:
        page = store.search_institutions(InstitutionFilters(limit=100, offset=offset))
        institutions.extend(page)
        if len(page) < 100:
            return institutions
        offset += len(page)


def _balanced_school_list(
    schools: list[SchoolReport],
    *,
    schools_per_category: int,
) -> list[SchoolReport]:
    selected: list[SchoolReport] = []
    selected_ids: set[int] = set()
    for category in AdmissionCategory:
        matching = [school for school in schools if school.classification.category is category]
        for school in matching[:schools_per_category]:
            selected.append(school)
            selected_ids.add(school.institution.unit_id)
    for school in schools:
        if school.user_entered and school.institution.unit_id not in selected_ids:
            selected.append(school)
    return selected


def _build_fixture_archive(csv_path: Path, archive_path: Path) -> None:
    temporary = archive_path.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(csv_path, arcname=_ARCHIVE_MEMBER)
        temporary.replace(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        temporary.unlink(missing_ok=True)
        raise StorageError("Could not build offline Scorecard fixture archive") from exc
