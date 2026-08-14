from pathlib import Path

import pytest

from phase0_analyzer.config import Settings
from phase0_analyzer.database import initialize_database
from phase0_analyzer.file_discovery import calculate_sha256, discover_files
from phase0_analyzer.file_parsing import FileParsingService
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.parsers.resolver import ParserResolver
from phase0_analyzer.snapshot import SnapshotError, SnapshotService


def make_repository(tmp_path: Path) -> tuple[FileRepository, Settings]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'snapshot.db'}",
        original_dir=tmp_path / "original",
        _env_file=None,
    )
    initialize_database(settings)
    return FileRepository(settings.database_path), settings


def test_registration_creates_verified_snapshot(tmp_path: Path) -> None:
    upload = tmp_path / "upload"
    upload.mkdir()
    source = upload / "orders.csv"
    source.write_text("受注番号,金額\nA1,100", encoding="utf-8")
    repository, _ = make_repository(tmp_path)
    snapshots = SnapshotService(tmp_path / "original")

    assert snapshots.register(discover_files(upload)[0], repository)
    stored = repository.list_all()[0]
    snapshot = Path(stored.original_snapshot_path or "")

    assert snapshot == tmp_path / "original" / str(stored.id) / source.name
    assert snapshot.read_bytes() == source.read_bytes()
    assert calculate_sha256(snapshot) == stored.sha256


def test_upload_change_does_not_change_old_snapshot_parse(tmp_path: Path) -> None:
    upload = tmp_path / "upload"
    upload.mkdir()
    source = upload / "orders.csv"
    source.write_text("受注番号,金額\nold,100", encoding="utf-8")
    repository, settings = make_repository(tmp_path)
    snapshots = SnapshotService(tmp_path / "original")
    snapshots.register(discover_files(upload)[0], repository)
    file_id = repository.list_all()[0].id
    source.write_text("受注番号,金額\nnew,200", encoding="utf-8")

    result = FileParsingService(repository, ParserResolver(settings)).parse(file_id)

    assert result.success
    assert "old,100" in result.extracted_text
    assert "new,200" not in result.extracted_text


def test_duplicate_registration_does_not_overwrite_snapshot(tmp_path: Path) -> None:
    upload = tmp_path / "upload"
    upload.mkdir()
    source = upload / "stock.csv"
    source.write_text("在庫,数量\nA,1", encoding="utf-8")
    repository, _ = make_repository(tmp_path)
    snapshots = SnapshotService(tmp_path / "original")
    discovered = discover_files(upload)[0]
    snapshots.register(discovered, repository)
    stored = repository.list_all()[0]
    snapshot = Path(stored.original_snapshot_path or "")
    before = snapshot.read_bytes()

    assert snapshots.register(discovered, repository) is False
    assert snapshot.read_bytes() == before


def test_copy_failure_leaves_no_file_row_or_snapshot(tmp_path: Path) -> None:
    upload = tmp_path / "upload"
    upload.mkdir()
    (upload / "orders.csv").write_text("受注", encoding="utf-8")
    repository, _ = make_repository(tmp_path)

    def fail_copy(source: Path, target: Path) -> object:
        raise OSError("copy failed")

    snapshots = SnapshotService(tmp_path / "original", copy_function=fail_copy)

    with pytest.raises(SnapshotError):
        snapshots.register(discover_files(upload)[0], repository)

    assert repository.count() == 0
    assert not list((tmp_path / "original").rglob("*.csv"))
