"""Offline end-to-end demo orchestration using only frozen public fixture data."""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from app.data import IPEDS_COMPLETIONS_YEAR
from app.exporting import export_college_report
from app.models import (
    AdmissionCategory,
    CategoryThresholdResult,
    ExportFormat,
    Institution,
    InstitutionFilters,
    MajorFitResult,
    RecommendationSettings,
    ReportCandidate,
    SchoolReport,
    StudentProfile,
    ThresholdMode,
    assess_profile,
)
from app.policies import apply_institution_policies
from app.ranking import FIT_METHODOLOGY_VERSION, rank_major_fits
from app.regional import is_regional_baseline
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
        institutions = apply_institution_policies(_load_all_institutions(college_store))
        dataset = college_store.current_dataset_version()
        offerings = college_store.get_program_offerings(
            [institution.unit_id for institution in institutions]
        )
    if dataset is None or not institutions:
        raise DemoError("Demo college database contains no usable institutions")

    existing = {name.casefold() for name in profile.preferences.existing_schools}
    preferred_states = set(profile.preferences.preferred_states)
    national_candidates = [
        ReportCandidate(
            institution=institution,
            user_entered=institution.name.casefold() in existing,
            regional_baseline=(
                profile.preferences.recommendation_settings.include_regional_baseline
                and is_regional_baseline(profile.preferences.residence_state, institution.name)
            ),
        )
        for institution in institutions
    ]
    candidates = [
        candidate
        for candidate in national_candidates
        if not preferred_states
        or candidate.institution.state in preferred_states
        or candidate.user_entered
        or candidate.regional_baseline
    ]
    complete_report = build_college_report(
        profile,
        candidates,
        dataset,
        generated_at=generated_at or datetime.now(UTC),
    )
    local_rankings, consolidated_rankings = rank_major_fits(
        profile, complete_report.schools, offerings
    )
    if len(candidates) == len(national_candidates):
        major_rankings = local_rankings
    else:
        national_report = build_college_report(
            profile,
            national_candidates,
            dataset,
            generated_at=generated_at or datetime.now(UTC),
        )
        nationwide_rankings, _ = rank_major_fits(profile, national_report.schools, offerings)
        major_rankings = _merge_national_ranks(local_rankings, nationwide_rankings)
    recommendation_settings = profile.preferences.recommendation_settings
    category_cap = min(
        schools_per_category,
        recommendation_settings.maximum_results_per_category,
    )
    selected_rankings, addendum_rankings, category_thresholds = _partition_major_rankings(
        complete_report.schools,
        major_rankings,
        intended_majors=profile.preferences.intended_majors,
        settings=recommendation_settings,
        schools_per_category=category_cap,
    )
    user_ids = {
        school.institution.unit_id for school in complete_report.schools if school.user_entered
    }
    student_supplied_rankings = [item for item in major_rankings if item.unit_id in user_ids]
    selected_ids = {result.unit_id for result in selected_rankings}
    selected_ids.update(user_ids)
    regional_ids = {
        school.institution.unit_id for school in complete_report.schools if school.regional_baseline
    }
    selected_ids.update(regional_ids)
    ranked_ids = {result.unit_id for result in selected_rankings}
    best_rank = {
        unit_id: min(item.rank for item in selected_rankings if item.unit_id == unit_id)
        for unit_id in ranked_ids
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
            "student_supplied_rankings": student_supplied_rankings,
            "major_rankings": selected_rankings,
            "addendum_rankings": addendum_rankings,
            "category_thresholds": category_thresholds,
            "consolidated_rankings": [
                result for result in consolidated_rankings if result.unit_id in selected_ids
            ][:10],
            "fit_methodology_version": FIT_METHODOLOGY_VERSION,
            "program_data_vintages": [
                "College Scorecard field-of-study "
                + (
                    dataset.release_date.isoformat() if dataset.release_date else "date unavailable"
                ),
                f"IPEDS Completions {IPEDS_COMPLETIONS_YEAR}",
            ],
            "data_quality_warnings": _data_quality_warnings(
                dataset.release_date, IPEDS_COMPLETIONS_YEAR
            ),
            "recommendation_warnings": [
                item.warning for item in category_thresholds if item.warning
            ],
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
        "addendum_rankings": len(report.addendum_rankings),
        "category_thresholds": [
            {
                "major": item.intended_major,
                "category": item.category.value,
                "applied": float(item.applied_threshold),
                "qualified": item.qualified_candidates,
            }
            for item in report.category_thresholds
        ],
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


def _data_quality_warnings(scorecard_release: date | None, ipeds_year: int) -> list[str]:
    if scorecard_release is None:
        return []
    age_days = (scorecard_release - date(ipeds_year, 12, 31)).days
    if age_days <= 548:
        return []
    return [
        f"Program availability uses IPEDS {ipeds_year}, which is more than 18 months older "
        f"than the College Scorecard release dated {scorecard_release.isoformat()}."
    ]


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


def _partition_major_rankings(
    schools: list[SchoolReport],
    rankings: list[MajorFitResult],
    *,
    intended_majors: list[str],
    settings: RecommendationSettings,
    schools_per_category: int,
) -> tuple[list[MajorFitResult], list[MajorFitResult], list[CategoryThresholdResult]]:
    user_ids = {school.institution.unit_id for school in schools if school.user_entered}
    selected: list[MajorFitResult] = []
    addendum: list[MajorFitResult] = []
    thresholds: list[CategoryThresholdResult] = []
    groups: dict[tuple[str, AdmissionCategory], list[MajorFitResult]] = {}
    for item in rankings:
        key = (item.intended_major, item.category)
        if (
            item.unit_id not in user_ids
            and item.program_offered is True
            and item.match_granularity == 6
        ):
            groups.setdefault(key, []).append(item)

    for major in intended_majors:
        for category in AdmissionCategory:
            candidates = groups.get((major, category), [])
            applied = _applied_threshold(candidates, settings)
            qualified = [item for item in candidates if item.overall_score >= applied]
            ranked = [
                item.model_copy(
                    update={
                        "rank": index,
                        "applied_fit_threshold": applied,
                    }
                )
                for index, item in enumerate(qualified, 1)
            ]
            selected.extend(ranked[:schools_per_category])
            addendum.extend(ranked[schools_per_category:])
            thresholds.append(
                CategoryThresholdResult(
                    intended_major=major,
                    category=category,
                    threshold_mode=settings.threshold_mode,
                    initial_threshold=settings.initial_fit_threshold,
                    applied_threshold=applied,
                    adaptive_floor=settings.adaptive_floor,
                    minimum_requested=settings.minimum_results_per_category,
                    exact_program_candidates=len(candidates),
                    qualified_candidates=len(qualified),
                    selected_candidates=min(len(qualified), schools_per_category),
                    addendum_candidates=max(0, len(qualified) - schools_per_category),
                    threshold_relaxed=applied < settings.initial_fit_threshold,
                    warning=(
                        f"{major} / {category.value.replace('_', ' ').title()}: fit threshold "
                        f"was relaxed from {settings.initial_fit_threshold} to {applied}; review "
                        "these options with greater caution."
                        if applied < settings.initial_fit_threshold
                        else None
                    ),
                )
            )
    return selected, addendum, thresholds


def _applied_threshold(
    candidates: list[MajorFitResult],
    settings: RecommendationSettings,
) -> Decimal:
    threshold = settings.initial_fit_threshold
    if settings.threshold_mode is ThresholdMode.FIXED:
        return threshold
    while (
        threshold > settings.adaptive_floor
        and sum(item.overall_score >= threshold for item in candidates)
        < settings.minimum_results_per_category
    ):
        threshold = max(settings.adaptive_floor, threshold - 1)
    return threshold


def _merge_national_ranks(
    local_rankings: list[MajorFitResult],
    nationwide_rankings: list[MajorFitResult],
) -> list[MajorFitResult]:
    national = {
        (item.unit_id, item.intended_major): (
            item.national_rank,
            item.national_rank_total,
            item.national_fit_top_percent,
            item.national_program_strength_rank,
            item.national_program_strength_rank_total,
            item.national_program_strength_top_percent,
        )
        for item in nationwide_rankings
    }
    return [
        item.model_copy(
            update={
                "national_rank": national[(item.unit_id, item.intended_major)][0],
                "national_rank_total": national[(item.unit_id, item.intended_major)][1],
                "national_program_strength_rank": national[(item.unit_id, item.intended_major)][3],
                "national_program_strength_rank_total": national[
                    (item.unit_id, item.intended_major)
                ][4],
                "national_fit_top_percent": national[(item.unit_id, item.intended_major)][2],
                "national_program_strength_top_percent": national[
                    (item.unit_id, item.intended_major)
                ][5],
            }
        )
        for item in local_rankings
    ]


def _build_fixture_archive(csv_path: Path, archive_path: Path, member: str) -> None:
    temporary = archive_path.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(csv_path, arcname=member)
        temporary.replace(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        temporary.unlink(missing_ok=True)
        raise StorageError("Could not build offline Scorecard fixture archive") from exc
