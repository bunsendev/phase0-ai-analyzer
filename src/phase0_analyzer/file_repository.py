"""Persistence operations for discovered file metadata."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from phase0_analyzer.database import connect
from phase0_analyzer.file_discovery import DiscoveredFile


@dataclass(frozen=True, slots=True)
class StoredFile:
    """One registered version of a discovered file."""

    id: int
    source_path: str
    file_name: str
    extension: str
    size_bytes: int
    modified_at: str
    registered_at: str
    sha256: str
    original_snapshot_path: str | None
    status: str


class FileRepository:
    """Append file identities and read the registration list."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def register(self, file: DiscoveredFile) -> bool:
        """Register a file identity once and return whether a row was added."""
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO files(
                    source_path,
                    file_name,
                    extension,
                    size_bytes,
                    modified_at,
                    sha256,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file.source_path,
                    file.file_name,
                    file.extension,
                    file.size_bytes,
                    file.modified_at,
                    file.sha256,
                    file.status,
                ),
            )
            return cursor.rowcount == 1

    def list_all(self) -> list[StoredFile]:
        """Return all registered file versions, newest registration first."""
        with connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    id,
                    source_path,
                    file_name,
                    extension,
                    size_bytes,
                    modified_at,
                    discovered_at AS registered_at,
                    sha256,
                    original_snapshot_path,
                    status
                FROM files
                ORDER BY discovered_at DESC, id DESC
                """
            ).fetchall()
        return [StoredFile(**dict(row)) for row in rows]

    def get_by_id(self, file_id: int) -> StoredFile | None:
        """Return the exact registered file version selected by its ID."""
        with connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    id,
                    source_path,
                    file_name,
                    extension,
                    size_bytes,
                    modified_at,
                    discovered_at AS registered_at,
                    sha256,
                    original_snapshot_path,
                    status
                FROM files
                WHERE id = ?
                """,
                (file_id,),
            ).fetchone()
        return StoredFile(**dict(row)) if row is not None else None

    def update_snapshot_path(self, file_id: int, snapshot_path: Path) -> None:
        """Set a previously missing immutable snapshot path once."""
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE files
                SET original_snapshot_path = ?
                WHERE id = ? AND original_snapshot_path IS NULL
                """,
                (str(snapshot_path), file_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("原本snapshotの保存先を更新できませんでした。")

    def update_status(self, file_id: int, status: str) -> None:
        """Update only the current file workflow status."""
        with connect(self.database_path) as connection:
            connection.execute("UPDATE files SET status = ? WHERE id = ?", (status, file_id))

    def count(self) -> int:
        """Return the number of registered file versions."""
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT COUNT(*) FROM files").fetchone()
        return int(row[0])
