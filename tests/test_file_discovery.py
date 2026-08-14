import hashlib
from pathlib import Path

from phase0_analyzer.file_discovery import discover_files


def test_discover_files_collects_identity_and_support_status(tmp_path: Path) -> None:
    supported = tmp_path / "受注.XLSX"
    unsupported = tmp_path / "memo.txt"
    supported.write_bytes(b"xlsx sample")
    unsupported.write_text("memo", encoding="utf-8")
    (tmp_path / ".gitkeep").touch()
    (tmp_path / "subdirectory").mkdir()

    discovered = discover_files(tmp_path)

    assert [file.file_name for file in discovered] == ["memo.txt", "受注.XLSX"]
    by_name = {file.file_name: file for file in discovered}
    assert by_name["受注.XLSX"].extension == "xlsx"
    assert by_name["受注.XLSX"].status == "READY"
    assert by_name["受注.XLSX"].size_bytes == len(b"xlsx sample")
    assert by_name["受注.XLSX"].sha256 == hashlib.sha256(b"xlsx sample").hexdigest()
    assert by_name["memo.txt"].status == "UNSUPPORTED"
