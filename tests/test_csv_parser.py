from pathlib import Path

from phase0_analyzer.parsers.csv_parser import CsvParser


def test_csv_parser_reads_utf8_and_records_structure(tmp_path: Path) -> None:
    path = tmp_path / "inventory.csv"
    path.write_text("商品,数量\n商品A,10\n商品B,20", encoding="utf-8")

    result = CsvParser().parse(1, path.name, path)

    assert result.success
    assert result.metadata["encoding"] == "utf-8"
    assert result.metadata["delimiter"] == ","
    assert result.metadata["row_count"] == 3
    assert result.metadata["column_count"] == 2
    assert result.metadata["header_candidate"] == ["商品", "数量"]


def test_csv_parser_reads_cp932_and_records_encoding(tmp_path: Path) -> None:
    path = tmp_path / "shipping.csv"
    path.write_bytes("配送先,個数\n東京,3".encode("cp932"))

    result = CsvParser().parse(2, path.name, path)

    assert result.success
    assert result.metadata["encoding"] == "cp932"
    assert "東京" in result.extracted_text


def test_csv_parser_records_utf8_bom_encoding(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_text("商品,数量\n商品A,10", encoding="utf-8-sig")

    result = CsvParser().parse(5, path.name, path)

    assert result.success
    assert result.metadata["encoding"] == "utf-8-sig"
    assert result.metadata["header_candidate"] == ["商品", "数量"]


def test_csv_column_mismatch_is_warning(tmp_path: Path) -> None:
    path = tmp_path / "mismatch.csv"
    path.write_text("a,b\n1,2\n3", encoding="utf-8")

    result = CsvParser().parse(3, path.name, path)

    assert result.success
    assert "CSV_COLUMN_COUNT_MISMATCH" in {warning.code for warning in result.warnings}


def test_unreadable_csv_returns_failure_without_raising(tmp_path: Path) -> None:
    path = tmp_path / "broken.csv"
    path.write_bytes(b"\x81")

    result = CsvParser().parse(4, path.name, path)

    assert not result.success
    assert result.error_code == "CSV_DECODE_FAILED"
    assert result.error_message
