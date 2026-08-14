"""Application settings loaded from environment variables and ``.env``."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Settings required by the task 1 application shell."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    upload_dir: Path = PROJECT_ROOT / "data" / "upload"
    original_dir: Path = PROJECT_ROOT / "data" / "original"
    work_dir: Path = PROJECT_ROOT / "data" / "work"
    database_url: str = "sqlite:///./data/database/phase0.db"
    ai_provider: str = Field(default="mock", pattern=r"^[a-zA-Z0-9_-]+$")
    pdf_text_threshold: int = Field(default=50, ge=0)
    pdf_max_pages: int = Field(default=10, ge=1)
    table_preview_max_rows: int = Field(default=30, ge=1, le=30)
    category_confidence_threshold: float = Field(default=0.80, ge=0, le=1)
    document_type_confidence_threshold: float = Field(default=0.70, ge=0, le=1)
    default_user: str = "phase0-user"
    log_level: str = "INFO"

    def resolve_path(self, path: Path) -> Path:
        """Resolve a configured path relative to the project root."""
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    @property
    def database_path(self) -> Path:
        """Return the filesystem path from a local SQLite URL."""
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("DATABASE_URLにはsqlite:///形式を指定してください。")
        raw_path = Path(self.database_url.removeprefix(prefix))
        return self.resolve_path(raw_path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings."""
    return Settings()
