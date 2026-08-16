from pathlib import Path

import pytest

from phase0_analyzer.config import Settings


def test_settings_can_be_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "upload"))
    monkeypatch.setenv("VALIDATION_DIR", str(tmp_path / "validation"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'phase0.db'}")
    monkeypatch.setenv("OCR_REVIEW_REQUIRED", "false")
    monkeypatch.setenv("AI_MAX_COLUMNS", "50")
    monkeypatch.setenv("AI_MAX_INPUT_CHARS", "50000")

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "mock"
    assert settings.resolve_path(settings.upload_dir) == tmp_path / "upload"
    assert settings.resolve_path(settings.validation_dir) == tmp_path / "validation"
    assert settings.database_path == tmp_path / "phase0.db"
    assert settings.ocr_review_required is False
    assert settings.ai_max_columns == 50
    assert settings.ai_max_input_chars == 50_000


def test_non_sqlite_database_url_has_japanese_error() -> None:
    settings = Settings(database_url="postgresql://localhost/example", _env_file=None)

    with pytest.raises(ValueError, match="sqlite"):
        _ = settings.database_path
