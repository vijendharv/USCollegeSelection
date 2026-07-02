"""Discover and download the latest official College Scorecard institution archive."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from app.networking import NetworkClient, NetworkError

SCORECARD_DATA_PAGE = "https://collegescorecard.ed.gov/data/"
_ARCHIVE_PATTERN = re.compile(r"Most-Recent-Cohorts-Institution[^/]*\.zip$", re.IGNORECASE)
_RELEASE_DATE_PATTERN = re.compile(r"_(\d{2})(\d{2})(\d{4})\.zip$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ScorecardDownload:
    archive_path: Path
    source_url: str
    retrieved_at: datetime
    release_date: date | None
    etag: str | None
    bytes_written: int


class ScorecardDataSource:
    """Use the networking boundary to retrieve the current federal archive."""

    def __init__(
        self,
        network: NetworkClient,
        raw_data_dir: Path,
        *,
        data_page_url: str = SCORECARD_DATA_PAGE,
    ) -> None:
        self.network = network
        self.raw_data_dir = raw_data_dir
        self.data_page_url = data_page_url

    def discover_latest_archive_url(self) -> str:
        html, metadata = self.network.get_text(self.data_page_url)
        parser = _ArchiveLinkParser()
        parser.feed(html)
        matches = [
            urljoin(metadata.url, href)
            for href in parser.hrefs
            if _ARCHIVE_PATTERN.search(urlparse(href).path)
        ]
        if len(matches) != 1:
            raise NetworkError(
                "Expected exactly one current institution archive on the College Scorecard page"
            )
        return matches[0]

    def download_latest(self) -> ScorecardDownload:
        source_url = self.discover_latest_archive_url()
        filename = Path(urlparse(source_url).path).name
        if not _ARCHIVE_PATTERN.fullmatch(filename):
            raise NetworkError("College Scorecard archive filename was not recognized")
        destination = self.raw_data_dir / filename
        result = self.network.download_file(source_url, destination)
        return ScorecardDownload(
            archive_path=result.destination,
            source_url=result.metadata.url,
            retrieved_at=result.metadata.retrieved_at,
            release_date=_release_date(filename),
            etag=result.metadata.etag,
            bytes_written=result.bytes_written,
        )


class _ArchiveLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def _release_date(filename: str) -> date | None:
    match = _RELEASE_DATE_PATTERN.search(filename)
    if not match:
        return None
    month, day, year = (int(value) for value in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None
