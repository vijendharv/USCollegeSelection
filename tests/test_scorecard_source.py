from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.data import ScorecardDataSource
from app.networking import NetworkError
from tests.fakes import FakeNetworkClient

DATA_PAGE = "https://collegescorecard.ed.gov/data/"
ARCHIVE_URL = (
    "https://ed-public-download.scorecard.network/downloads/"
    "Most-Recent-Cohorts-Institution_06102026.zip"
)
FIELD_ARCHIVE_URL = (
    "https://ed-public-download.scorecard.network/downloads/"
    "Most-Recent-Cohorts-Field-of-Study_06102026.zip"
)


def page_with_link(link: str) -> str:
    return f'<html><body><a href="{link}">Download</a></body></html>'


def test_discovers_and_downloads_current_institution_archive(tmp_path: Path) -> None:
    network = FakeNetworkClient(
        {
            DATA_PAGE: page_with_link(ARCHIVE_URL),
            ARCHIVE_URL: "archive-bytes",
        }
    )
    source = ScorecardDataSource(network, tmp_path / "raw")

    download = source.download_latest()

    assert download.source_url == ARCHIVE_URL
    assert download.release_date == date(2026, 6, 10)
    assert download.archive_path.read_text(encoding="utf-8") == "archive-bytes"


def test_discovery_rejects_missing_or_ambiguous_archive_links(tmp_path: Path) -> None:
    network = FakeNetworkClient({DATA_PAGE: "<html>No archive</html>"})

    with pytest.raises(NetworkError, match="exactly one"):
        ScorecardDataSource(network, tmp_path).discover_latest_archive_url()


def test_discovers_and_downloads_current_field_archive(tmp_path: Path) -> None:
    network = FakeNetworkClient(
        {
            DATA_PAGE: page_with_link(FIELD_ARCHIVE_URL),
            FIELD_ARCHIVE_URL: "field-archive-bytes",
        }
    )

    download = ScorecardDataSource(network, tmp_path / "raw").download_latest_field_of_study()

    assert download.source_url == FIELD_ARCHIVE_URL
    assert download.release_date == date(2026, 6, 10)
