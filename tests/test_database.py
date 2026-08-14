import sqlite3
from pathlib import Path

from phase0_analyzer.config import Settings
from phase0_analyzer.database import initialize_database


EXPECTED_TABLES = {
    "analysis_results",
    "ai_results",
    "analysis_runs",
    "confirmed_results",
    "confirmed_fields",
    "correction_history",
    "extracted_fields",
    "files",
    "schema_metadata",
    "warnings",
}


def test_initialize_database_creates_required_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "database" / "test.db"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        _env_file=None,
    )

    assert initialize_database(settings) == database_path

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        schema_versions = connection.execute(
            "SELECT version FROM schema_metadata"
        ).fetchall()

    assert EXPECTED_TABLES <= tables
    assert schema_versions == [(4,)]


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        _env_file=None,
    )

    initialize_database(settings)
    initialize_database(settings)

    with sqlite3.connect(settings.database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM schema_metadata").fetchone()

    assert count == (1,)


def test_initialize_database_migrates_day1_files_table(tmp_path: Path) -> None:
    database_path = tmp_path / "day1.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_metadata (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO schema_metadata(version) VALUES (1);
            CREATE TABLE files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                modified_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'READY'
            );
            """
        )
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        _env_file=None,
    )

    initialize_database(settings)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(files)")
        }
        versions = connection.execute(
            "SELECT version FROM schema_metadata ORDER BY version"
        ).fetchall()

    assert "sha256" in columns
    assert versions == [(1,), (4,)]
