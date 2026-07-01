from __future__ import annotations

from pathlib import Path

import pytest

from app.networking import NetworkClient
from tests.fakes import FakeNetworkClient


def accepts_network_client(client: NetworkClient, destination: Path) -> str:
    result = client.download_file("https://example.test/data", destination)
    return result.destination.read_text(encoding="utf-8")


def test_fake_network_client_implements_boundary(tmp_path: Path) -> None:
    client = FakeNetworkClient({"https://example.test/data": "college-data"})

    assert accepts_network_client(client, tmp_path / "data.csv") == "college-data"


def test_http_client_rejects_local_file_scheme() -> None:
    from app.networking import HttpClient, NetworkError

    with HttpClient() as client, pytest.raises(NetworkError, match="HTTP and HTTPS"):
        client.get_text("file:///etc/passwd")
