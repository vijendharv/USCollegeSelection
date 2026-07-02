"""Download the current pinned IPEDS six-digit completions release."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.networking import NetworkClient

IPEDS_COMPLETIONS_YEAR = 2024
IPEDS_COMPLETIONS_URL = "https://nces.ed.gov/ipeds/datacenter/data/C2024_A.zip"


@dataclass(frozen=True, slots=True)
class IPEDSDownload:
    archive_path: Path
    source_url: str
    retrieved_at: datetime
    year: int
    bytes_written: int


class IPEDSDataSource:
    """Retrieve the pinned final/provisional IPEDS Completions archive."""

    def __init__(self, network: NetworkClient, raw_data_dir: Path) -> None:
        self.network = network
        self.raw_data_dir = raw_data_dir

    def download_latest_completions(self) -> IPEDSDownload:
        destination = self.raw_data_dir / f"C{IPEDS_COMPLETIONS_YEAR}_A.zip"
        result = self.network.download_file(IPEDS_COMPLETIONS_URL, destination)
        return IPEDSDownload(
            archive_path=result.destination,
            source_url=result.metadata.url,
            retrieved_at=result.metadata.retrieved_at,
            year=IPEDS_COMPLETIONS_YEAR,
            bytes_written=result.bytes_written,
        )
