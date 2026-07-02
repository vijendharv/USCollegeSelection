from __future__ import annotations

from pathlib import Path

import pytest

from app.storage import CollegeStore, LocalSessionFileStore, StorageError
from tests.fakes import FakeCollegeStore


def check_college_store(store: CollegeStore) -> bool:
    return store.healthcheck()


def test_fake_college_store_implements_boundary() -> None:
    assert check_college_store(FakeCollegeStore()) is True


def test_local_session_store_creates_and_deletes_session(tmp_path: Path) -> None:
    store = LocalSessionFileStore(tmp_path / "sessions")

    session_id, path = store.create_session()
    (path / "report.pdf").write_bytes(b"report")
    store.delete_session(session_id)

    assert not path.exists()


def test_local_session_store_rejects_unsafe_id(tmp_path: Path) -> None:
    store = LocalSessionFileStore(tmp_path / "sessions")

    with pytest.raises(StorageError, match="Invalid session ID"):
        store.session_path("../outside")


def test_session_file_store_atomically_writes_private_generated_file(tmp_path: Path) -> None:
    store = LocalSessionFileStore(tmp_path)
    session_id, _ = store.create_session()

    path = store.write_file(session_id, "college-report.pdf", b"report")

    assert path.read_bytes() == b"report"
    assert path.stat().st_mode & 0o777 == 0o600


def test_session_file_store_rejects_unsafe_generated_filename(tmp_path: Path) -> None:
    store = LocalSessionFileStore(tmp_path)
    session_id, _ = store.create_session()

    with pytest.raises(StorageError, match="Invalid session filename"):
        store.write_file(session_id, "../report.pdf", b"report")
