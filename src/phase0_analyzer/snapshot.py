"""Immutable original-file snapshot creation and recovery."""

import shutil
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from phase0_analyzer.database import connect
from phase0_analyzer.file_discovery import DiscoveredFile, calculate_sha256
from phase0_analyzer.file_repository import FileRepository


class SnapshotError(RuntimeError):
    """A safe Japanese error raised when a snapshot cannot be completed."""


CopyFunction = Callable[[Path, Path], object]


class SnapshotService:
    """Create non-overwriting snapshots tied to files.id."""

    def __init__(
        self,
        original_dir: Path,
        copy_function: CopyFunction = shutil.copy2,
    ) -> None:
        self.original_dir = original_dir
        self.copy_function = copy_function

    def register(self, file: DiscoveredFile, repository: FileRepository) -> bool:
        """Atomically register metadata and its verified snapshot."""
        target: Path | None = None
        temporary: Path | None = None
        created_target = False
        try:
            with connect(repository.database_path) as connection:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO files(
                        source_path, file_name, extension, size_bytes,
                        modified_at, sha256, status
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
                if cursor.rowcount == 0:
                    return False
                file_id = int(cursor.lastrowid)
                target = self.original_dir / str(file_id) / file.file_name
                temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise SnapshotError("同じファイルIDの原本snapshotが既に存在します。")
                source = Path(file.source_path)
                if calculate_sha256(source) != file.sha256:
                    raise SnapshotError("登録中に元ファイルの内容が変更されました。")
                self.copy_function(source, temporary)
                if calculate_sha256(temporary) != file.sha256:
                    raise SnapshotError("原本snapshotのSHA-256が一致しません。")
                temporary.rename(target)
                created_target = True
                connection.execute(
                    "UPDATE files SET original_snapshot_path = ? WHERE id = ?",
                    (str(target.resolve()), file_id),
                )
            return True
        except SnapshotError:
            raise
        except OSError as error:
            raise SnapshotError("原本snapshotを保存できませんでした。") from error
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
            if created_target and target is not None and not self._is_registered(
                repository, target
            ):
                target.unlink(missing_ok=True)
            if target is not None and target.parent.exists():
                try:
                    target.parent.rmdir()
                except OSError:
                    pass

    def ensure(self, file_id: int, repository: FileRepository) -> Path:
        """Return a verified snapshot, backfilling a legacy row when safe."""
        stored = repository.get_by_id(file_id)
        if stored is None:
            raise SnapshotError("指定されたファイルIDが見つかりません。")
        if stored.original_snapshot_path:
            snapshot = Path(stored.original_snapshot_path)
            if snapshot.is_file() and calculate_sha256(snapshot) == stored.sha256:
                return snapshot
            raise SnapshotError("登録済みの原本snapshotを確認できません。")

        source = Path(stored.source_path)
        if not source.is_file() or calculate_sha256(source) != stored.sha256:
            raise SnapshotError("登録時の内容と一致しないため原本snapshotを作成できません。")
        target = self.original_dir / str(file_id) / stored.file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise SnapshotError("未登録の原本snapshotが既に存在します。")
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            self.copy_function(source, temporary)
            if calculate_sha256(temporary) != stored.sha256:
                raise SnapshotError("原本snapshotのSHA-256が一致しません。")
            temporary.rename(target)
            repository.update_snapshot_path(file_id, target.resolve())
            return target.resolve()
        except Exception:
            temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise

    @staticmethod
    def _is_registered(repository: FileRepository, target: Path) -> bool:
        with connect(repository.database_path) as connection:
            row = connection.execute(
                "SELECT 1 FROM files WHERE original_snapshot_path = ?",
                (str(target.resolve()),),
            ).fetchone()
        return row is not None
