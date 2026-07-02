from __future__ import annotations

from pathlib import Path

from app.data import IPEDS_COMPLETIONS_URL, IPEDS_COMPLETIONS_YEAR, IPEDSDataSource
from tests.fakes import FakeNetworkClient


def test_downloads_pinned_ipeds_six_digit_completions(tmp_path: Path) -> None:
    network = FakeNetworkClient({IPEDS_COMPLETIONS_URL: "ipeds-archive-bytes"})

    download = IPEDSDataSource(network, tmp_path / "raw").download_latest_completions()

    assert download.year == IPEDS_COMPLETIONS_YEAR == 2024
    assert download.source_url == IPEDS_COMPLETIONS_URL
    assert download.archive_path.read_text(encoding="utf-8") == "ipeds-archive-bytes"
