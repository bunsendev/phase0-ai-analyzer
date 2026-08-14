from pathlib import Path

import pytest

from phase0_analyzer.config import Settings


def test_settings_can_be_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "upload"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'phase0.db'}")

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "mock"
    assert settings.resolve_path(settings.upload_dir) == tmp_path / "upload"
    assert settings.database_path == tmp_path / "phase0.db"


def test_non_sqlite_database_url_has_japanese_error() -> None:
    settings = Settings(database_url="postgresql://localhost/example", _env_file=None)

    with pytest.raises(ValueError, match="sqlite"):
        _ = settings.database_path
