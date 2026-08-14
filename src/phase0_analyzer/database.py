"""SQLite schema initialization for append-only analysis history."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from phase0_analyzer.config import Settings


SCHEMA_VERSION = 4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_metadata (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_at TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    original_snapshot_path TEXT,
    status TEXT NOT NULL DEFAULT 'READY'
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id),
    status TEXT NOT NULL,
    provider TEXT NOT NULL,
    run_number INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    duration_ms INTEGER,
    model_name TEXT,
    extracted_text TEXT,
    raw_ai_response TEXT,
    error_code TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    category_code TEXT NOT NULL,
    category_label TEXT NOT NULL,
    category_confidence REAL NOT NULL,
    category_reason TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_type_confidence REAL NOT NULL,
    provider_name TEXT,
    target_date TEXT,
    summary TEXT NOT NULL,
    needs_review INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extracted_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    source_name TEXT NOT NULL,
    common_name TEXT,
    normalized_name TEXT,
    extracted_value TEXT,
    corrected_value TEXT,
    data_type TEXT,
    confidence REAL,
    requires_review INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS correction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    extracted_field_id INTEGER REFERENCES extracted_fields(id),
    field_name TEXT NOT NULL,
    value_before TEXT,
    value_after TEXT,
    corrected_by TEXT NOT NULL,
    corrected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS confirmed_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    result_json TEXT NOT NULL,
    confirmed_by TEXT NOT NULL,
    confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS confirmed_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    confirmed_result_id INTEGER NOT NULL REFERENCES confirmed_results(id),
    extracted_field_id INTEGER NOT NULL REFERENCES extracted_fields(id),
    normalized_name TEXT,
    confirmed_value TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

"""


def _migrate_files_table(connection: sqlite3.Connection) -> None:
    """Add Day 2 identity data to a database created by schema version 1."""
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(files)").fetchall()
    }
    if "sha256" not in columns:
        connection.execute("ALTER TABLE files ADD COLUMN sha256 TEXT")
    if "original_snapshot_path" not in columns:
        connection.execute("ALTER TABLE files ADD COLUMN original_snapshot_path TEXT")

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_files_identity
        ON files(source_path, size_bytes, modified_at, sha256)
        """
    )


def _add_columns(
    connection: sqlite3.Connection, table: str, columns: dict[str, str]
) -> None:
    existing = {
        row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _migrate_day4_tables(connection: sqlite3.Connection) -> None:
    _add_columns(
        connection,
        "analysis_runs",
        {
            "run_number": "INTEGER",
            "duration_ms": "INTEGER",
            "model_name": "TEXT",
            "extracted_text": "TEXT",
            "raw_ai_response": "TEXT",
            "error_code": "TEXT",
        },
    )


def _migrate_day5_tables(connection: sqlite3.Connection) -> None:
    _add_columns(
        connection,
        "correction_history",
        {
            "file_id": "INTEGER REFERENCES files(id)",
            "analysis_result_id": "INTEGER REFERENCES analysis_results(id)",
            "target_type": "TEXT",
            "target_id": "INTEGER",
        },
    )
    _add_columns(
        connection,
        "confirmed_results",
        {
            "file_id": "INTEGER REFERENCES files(id)",
            "analysis_result_id": "INTEGER REFERENCES analysis_results(id)",
            "confirmed_category_code": "TEXT",
            "confirmed_document_type": "TEXT",
            "confirmed_provider_name": "TEXT",
            "confirmed_target_date": "TEXT",
        },
    )
    _add_columns(
        connection,
        "extracted_fields",
        {
            "normalized_name": "TEXT",
            "corrected_value": "TEXT",
            "needs_review": "INTEGER NOT NULL DEFAULT 0",
            "review_reason": "TEXT",
        },
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_runs_file_run
        ON analysis_runs(file_id, run_number)
        """
    )


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with foreign keys enabled."""
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database(settings: Settings) -> Path:
    """Create the database directory and the task 1 schema when absent."""
    database_path = settings.database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with connect(database_path) as connection:
        connection.executescript(SCHEMA_SQL)
        _migrate_files_table(connection)
        _migrate_day4_tables(connection)
        _migrate_day5_tables(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_metadata(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )

    return database_path
