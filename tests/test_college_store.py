from __future__ import annotations

import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.models import InstitutionFilters, Ownership
from app.storage import DuckDBCollegeStore, StorageError

FIXTURE = Path("tests/fixtures/scorecard/institutions.csv")
SOURCE_URL = (
    "https://ed-public-download.scorecard.network/downloads/"
    "Most-Recent-Cohorts-Institution_06102026.zip"
)
RETRIEVED_AT = datetime(2026, 7, 1, 12, tzinfo=UTC)


def make_archive(tmp_path: Path, csv_path: Path = FIXTURE) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    archive_path = tmp_path / "scorecard.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(csv_path, "Most-Recent-Cohorts-Institution.csv")
    return archive_path


def refresh_fixture(store: DuckDBCollegeStore, archive_path: Path) -> None:
    store.refresh_from_scorecard_zip(
        archive_path,
        source_url=SOURCE_URL,
        retrieved_at=RETRIEVED_AT,
        release_date=date(2026, 6, 10),
        minimum_eligible_institutions=6,
    )


def test_refresh_builds_valid_database_from_frozen_public_data(tmp_path: Path) -> None:
    database = tmp_path / "college.duckdb"
    archive = make_archive(tmp_path)

    with DuckDBCollegeStore(database, read_only=False) as store:
        report = store.refresh_from_scorecard_zip(
            archive,
            source_url=SOURCE_URL,
            retrieved_at=RETRIEVED_AT,
            release_date=date(2026, 6, 10),
            minimum_eligible_institutions=6,
        )

        assert store.healthcheck()
        assert report.dataset.raw_row_count == 8
        assert report.dataset.eligible_row_count == 6
        assert report.dataset.release_date == date(2026, 6, 10)

    with DuckDBCollegeStore(database) as store:
        harvard = store.get_institution(166027)
        assert harvard is not None
        assert harvard.name == "Harvard University"
        assert harvard.ownership is Ownership.PRIVATE_NONPROFIT
        assert harvard.acceptance_rate == pytest.approx(0.0365)
        assert harvard.average_net_price == 19066
        assert store.get_institution(121044) is None
        assert store.get_institution(110398) is None
        colegio = store.get_institution(241720)
        assert colegio is not None
        assert colegio.average_net_price is None


def test_search_supports_basic_filters_and_pagination(tmp_path: Path) -> None:
    database = tmp_path / "college.duckdb"
    archive = make_archive(tmp_path)
    with DuckDBCollegeStore(database, read_only=False) as writer:
        refresh_fixture(writer, archive)

    with DuckDBCollegeStore(database) as store:
        california_public = store.search_institutions(
            InstitutionFilters(states=["CA"], ownership=[Ownership.PUBLIC])
        )
        selective = store.search_institutions(
            InstitutionFilters(minimum_acceptance_rate=0, maximum_tuition=40_000, limit=2)
        )
        by_name = store.search_institutions(InstitutionFilters(name_contains="Georgia"))

    assert [school.unit_id for school in california_public] == [110635]
    assert len(selective) == 2
    assert [school.unit_id for school in by_name] == [139755]


def test_dataset_version_is_queryable(tmp_path: Path) -> None:
    database = tmp_path / "college.duckdb"
    archive = make_archive(tmp_path)
    with DuckDBCollegeStore(database, read_only=False) as writer:
        refresh_fixture(writer, archive)

    with DuckDBCollegeStore(database) as store:
        version = store.current_dataset_version()

    assert version is not None
    assert version.source_url == SOURCE_URL
    assert version.sha256
    assert version.schema_version == 2


def test_program_offerings_are_loaded_from_scorecard_cip_families(tmp_path: Path) -> None:
    database = tmp_path / "college.duckdb"
    archive = make_archive(tmp_path)
    with DuckDBCollegeStore(database, read_only=False) as writer:
        refresh_fixture(writer, archive)

    with DuckDBCollegeStore(database) as store:
        offerings = store.get_program_offerings([139755])

    assert {item.cip_code for item in offerings} == {"11", "14", "26", "40"}
    engineering = next(item for item in offerings if item.cip_code == "14")
    assert engineering.share_of_awards == pytest.approx(0.55)


def test_failed_refresh_preserves_existing_database(tmp_path: Path) -> None:
    database = tmp_path / "college.duckdb"
    archive = make_archive(tmp_path)
    with DuckDBCollegeStore(database, read_only=False) as writer:
        refresh_fixture(writer, archive)

    invalid_csv = tmp_path / "invalid.csv"
    invalid_csv.write_text("UNITID,INSTNM\n1,Broken\n", encoding="utf-8")
    invalid_archive = make_archive(tmp_path / "invalid", invalid_csv)

    with (
        DuckDBCollegeStore(database, read_only=False) as writer,
        pytest.raises(StorageError, match="missing required columns"),
    ):
        refresh_fixture(writer, invalid_archive)

    with DuckDBCollegeStore(database) as store:
        assert store.healthcheck()
        assert store.get_institution(166027) is not None


def test_read_only_store_cannot_refresh(tmp_path: Path) -> None:
    store = DuckDBCollegeStore(tmp_path / "college.duckdb")

    with pytest.raises(StorageError, match="read-only"):
        refresh_fixture(store, make_archive(tmp_path))
