from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings


def test_settings_read_prefixed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USCS_ENVIRONMENT", "test")
    monkeypatch.setenv("USCS_DATA_DIR", str(tmp_path / "college-data"))

    settings = Settings()

    assert settings.environment == "test"
    assert settings.data_dir == tmp_path / "college-data"
