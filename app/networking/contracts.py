"""Typed networking boundary shared by application services and tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


class NetworkError(RuntimeError):
    """A stable application error for failed or unsafe network operations."""


@dataclass(frozen=True, slots=True)
class ResponseMetadata:
    url: str
    status_code: int
    retrieved_at: datetime
    etag: str | None = None


@dataclass(frozen=True, slots=True)
class DownloadResult:
    destination: Path
    bytes_written: int
    metadata: ResponseMetadata


class NetworkClient(Protocol):
    """The intentionally small outbound-network interface."""

    def get_text(self, url: str) -> tuple[str, ResponseMetadata]: ...

    def get_json(self, url: str) -> tuple[Any, ResponseMetadata]: ...

    def download_file(self, url: str, destination: Path) -> DownloadResult: ...
