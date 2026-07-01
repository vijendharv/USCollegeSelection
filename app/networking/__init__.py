"""Networking boundary for all outbound HTTP access."""

from app.networking.client import HttpClient
from app.networking.contracts import (
    DownloadResult,
    NetworkClient,
    NetworkError,
    ResponseMetadata,
)

__all__ = [
    "DownloadResult",
    "HttpClient",
    "NetworkClient",
    "NetworkError",
    "ResponseMetadata",
]
