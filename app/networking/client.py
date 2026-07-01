"""Concrete HTTP implementation of the networking boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.networking.contracts import DownloadResult, NetworkError, ResponseMetadata


class HttpClient:
    """Small synchronous HTTP client with consistent safety limits."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 1_000_000_000,
        user_agent: str = "USCollegeSelection/0.1",
    ) -> None:
        self._max_response_bytes = max_response_bytes
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_text(self, url: str) -> tuple[str, ResponseMetadata]:
        response = self._request("GET", url)
        self._check_content_length(response)
        content = response.content
        self._check_size(len(content))
        return response.text, self._metadata(response)

    def get_json(self, url: str) -> tuple[Any, ResponseMetadata]:
        text, metadata = self.get_text(url)
        try:
            return json.loads(text), metadata
        except json.JSONDecodeError as exc:
            raise NetworkError(f"Response from {url} was not valid JSON") from exc

    def download_file(self, url: str, destination: Path) -> DownloadResult:
        self._validate_url(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = 0
        try:
            with self._client.stream("GET", url) as response:
                response.raise_for_status()
                self._check_content_length(response)
                with destination.open("wb") as output:
                    for chunk in response.iter_bytes():
                        bytes_written += len(chunk)
                        self._check_size(bytes_written)
                        output.write(chunk)
                metadata = self._metadata(response)
        except (httpx.HTTPError, OSError) as exc:
            destination.unlink(missing_ok=True)
            raise NetworkError(f"Failed to download {url}") from exc
        return DownloadResult(destination, bytes_written, metadata)

    def _request(self, method: str, url: str) -> httpx.Response:
        self._validate_url(url)
        try:
            response = self._client.request(method, url)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise NetworkError(f"Request failed for {url}") from exc

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise NetworkError("Only absolute HTTP and HTTPS URLs are allowed")

    def _check_content_length(self, response: httpx.Response) -> None:
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self._max_response_bytes:
            raise NetworkError("Response exceeds the configured size limit")

    def _check_size(self, size: int) -> None:
        if size > self._max_response_bytes:
            raise NetworkError("Response exceeds the configured size limit")

    @staticmethod
    def _metadata(response: httpx.Response) -> ResponseMetadata:
        return ResponseMetadata(
            url=str(response.url),
            status_code=response.status_code,
            retrieved_at=datetime.now(UTC),
            etag=response.headers.get("etag"),
        )
