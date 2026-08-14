import os
from pathlib import Path

from phase0_analyzer.config import Settings
from phase0_analyzer.database import initialize_database
from phase0_analyzer.file_registration import register_discovered_files
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.snapshot import SnapshotService


def create_repository(tmp_path: Path) -> FileRepository:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'files.db'}", _env_file=None
    )
    initialize_database(settings)
    return FileRepository(settings.database_path)


def test_registers_supported_and_unsupported_files(tmp_path: Path) -> None:
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    (upload_dir / "inventory.csv").write_text("item,count\nA,1", encoding="utf-8")
    (upload_dir / "notes.docx").write_bytes(b"unsupported")
    repository = create_repository(tmp_path)

    summary = register_discovered_files(
        upload_dir, repository, SnapshotService(tmp_path / "original")
    )
    files = repository.list_all()

    assert summary.detected_count == 2
    assert summary.registered_count == 2
    assert summary.duplicate_count == 0
    assert {file.status for file in files} == {"READY", "UNSUPPORTED"}


def test_same_identity_is_not_registered_twice(tmp_path: Path) -> None:
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    (upload_dir / "shipping.pdf").write_bytes(b"pdf")
    repository = create_repository(tmp_path)

    snapshots = SnapshotService(tmp_path / "original")
    first = register_discovered_files(upload_dir, repository, snapshots)
    second = register_discovered_files(upload_dir, repository, snapshots)

    assert first.registered_count == 1
    assert second.registered_count == 0
    assert second.duplicate_count == 1
    assert repository.count() == 1


def test_changed_file_is_registered_as_new_version(tmp_path: Path) -> None:
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    file_path = upload_dir / "stock.csv"
    file_path.write_bytes(b"one")
    repository = create_repository(tmp_path)
    snapshots = SnapshotService(tmp_path / "original")
    register_discovered_files(upload_dir, repository, snapshots)

    file_path.write_bytes(b"two")
    original_mtime = file_path.stat().st_mtime
    os.utime(file_path, (original_mtime + 2, original_mtime + 2))
    summary = register_discovered_files(upload_dir, repository, snapshots)

    assert summary.registered_count == 1
    assert repository.count() == 2
