"""Local filesystem implementation for short-lived session files."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from app.storage.contracts import StorageError

_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class LocalSessionFileStore:
    """Manage session directories beneath one configured root."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> tuple[str, Path]:
        session_id = uuid4().hex
        path = self._root / session_id
        path.mkdir(mode=0o700)
        return session_id, path

    def session_path(self, session_id: str) -> Path:
        if not _SESSION_ID.fullmatch(session_id):
            raise StorageError("Invalid session ID")
        path = (self._root / session_id).resolve()
        if path.parent != self._root:
            raise StorageError("Session path escapes the configured root")
        return path

    def delete_session(self, session_id: str) -> None:
        path = self.session_path(session_id)
        if path.exists():
            shutil.rmtree(path)

    def write_file(self, session_id: str, filename: str, content: bytes) -> Path:
        """Atomically write one generated file inside an existing session."""
        if not _FILENAME.fullmatch(filename):
            raise StorageError("Invalid session filename")
        directory = self.session_path(session_id)
        if not directory.is_dir():
            raise StorageError("Session does not exist")
        destination = directory / filename
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
            temporary.replace(destination)
            destination.chmod(0o600)
            return destination
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
