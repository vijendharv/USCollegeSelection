from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli import health, main
from app.config import Settings


def test_health_creates_configured_directories(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", session_dir=tmp_path / "sessions")

    result = health(settings)

    assert result["status"] == "ok"
    assert settings.data_dir.is_dir()
    assert settings.session_dir.is_dir()


def test_health_command_prints_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("USCS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("USCS_SESSION_DIR", str(tmp_path / "sessions"))

    assert main(["health"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["service"] == "us-college-selection"
