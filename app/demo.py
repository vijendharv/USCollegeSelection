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
    ExportFormat,
    Institution,
    InstitutionFilters,
    MajorFitResult,
    ReportCandidate,
    SchoolReport,
    StudentProfile,
    assess_profile,
)
from app.ranking import FIT_METHODOLOGY_VERSION, rank_major_fits
from app.reporting import build_college_report
from app.storage import DuckDBCollegeStore, LocalSessionFileStore, StorageError

_FIXTURE_SOURCE_URL = "https://collegescorecard.ed.gov/data/"
_FIXTURE_RELEASE_DATE = date(2026, 6, 10)
_ARCHIVE_MEMBER = "Most-Recent-Cohorts-Institution.csv"
_FIELD_ARCHIVE_MEMBER = "Most-Recent-Cohorts-Field-of-Study.csv"
_IPEDS_ARCHIVE_MEMBER = "C2024_a.csv"


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
        _build_fixture_archive(fixture_csv_path, archive_path, _ARCHIVE_MEMBER)
        field_fixture = fixture_csv_path.parent / "fields.csv"
        ipeds_fixture = fixture_csv_path.parent / "ipeds-completions.csv"
        field_archive = database_path.parent / "demo-scorecard-fields.zip"
        ipeds_archive = database_path.parent / "demo-ipeds-completions.zip"
        if field_fixture.is_file():
            _build_fixture_archive(field_fixture, field_archive, _FIELD_ARCHIVE_MEMBER)
        if ipeds_fixture.is_file():
            _build_fixture_archive(ipeds_fixture, ipeds_archive, _IPEDS_ARCHIVE_MEMBER)
        with DuckDBCollegeStore(database_path, read_only=False) as store:
            store.refresh_from_scorecard_zip(
                archive_path,
                source_url=_FIXTURE_SOURCE_URL,
                retrieved_at=generated_at or datetime.now(UTC),
                release_date=_FIXTURE_RELEASE_DATE,
                field_archive_path=field_archive if field_fixture.is_file() else None,
                ipeds_archive_path=ipeds_archive if ipeds_fixture.is_file() else None,
                minimum_eligible_institutions=1,
            )

    with DuckDBCollegeStore(database_path) as college_store:
        institutions = _load_all_institutions(college_store)
        dataset = college_store.current_dataset_version()
        offerings = college_store.get_program_offerings(
            [institution.unit_id for institution in institutions]
        )
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
    major_rankings, consolidated_rankings = rank_major_fits(
        profile, complete_report.schools, offerings
    )
    selected_rankings = _selected_major_rankings(
        complete_report.schools,
        major_rankings,
        schools_per_category=schools_per_category,
    )
    selected_ids = {result.unit_id for result in selected_rankings}
    selected_ids.update(
        school.institution.unit_id for school in complete_report.schools if school.user_entered
    )
    best_rank = {
        unit_id: min(item.rank for item in selected_rankings if item.unit_id == unit_id)
        for unit_id in selected_ids
    }
    report = complete_report.model_copy(
        update={
            "schools": sorted(
                (
                    school
                    for school in complete_report.schools
                    if school.institution.unit_id in selected_ids
                ),
                key=lambda school: (
                    best_rank.get(school.institution.unit_id, 10_000),
                    school.institution.unit_id,
                ),
            ),
            "major_rankings": selected_rankings,
            "consolidated_rankings": [
                result for result in consolidated_rankings if result.unit_id in selected_ids
            ][:10],
            "fit_methodology_version": FIT_METHODOLOGY_VERSION,
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
        "fit_ranked": True,
        "fit_methodology_version": FIT_METHODOLOGY_VERSION,
        "major_rankings": len(report.major_rankings),
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


def _selected_major_rankings(
    schools: list[SchoolReport],
    rankings: list[MajorFitResult],
    *,
    schools_per_category: int,
) -> list[MajorFitResult]:
    selected = [item for item in rankings if item.rank <= schools_per_category]
    user_ids = {school.institution.unit_id for school in schools if school.user_entered}
    selected_keys = {(item.unit_id, item.intended_major) for item in selected}
    selected.extend(
        item
        for item in rankings
        if item.unit_id in user_ids and (item.unit_id, item.intended_major) not in selected_keys
    )
    return selected


def _build_fixture_archive(csv_path: Path, archive_path: Path, member: str) -> None:
    temporary = archive_path.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(csv_path, arcname=member)
        temporary.replace(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        temporary.unlink(missing_ok=True)
        raise StorageError("Could not build offline Scorecard fixture archive") from exc
