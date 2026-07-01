"""Small test doubles for the networking and storage boundaries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.networking import DownloadResult, ResponseMetadata


class FakeNetworkClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses

    def _response(self, url: str) -> tuple[str, ResponseMetadata]:
        return self.responses[url], ResponseMetadata(url, 200, datetime.now(UTC))

    def get_text(self, url: str) -> tuple[str, ResponseMetadata]:
        return self._response(url)

    def get_json(self, url: str) -> tuple[Any, ResponseMetadata]:
        text, metadata = self._response(url)
        return json.loads(text), metadata

    def download_file(self, url: str, destination: Path) -> DownloadResult:
        text, metadata = self._response(url)
        destination.write_text(text, encoding="utf-8")
        return DownloadResult(destination, len(text.encode()), metadata)


class FakeCollegeStore:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy
        self.closed = False

    def healthcheck(self) -> bool:
        return self.healthy

    def close(self) -> None:
        self.closed = True
