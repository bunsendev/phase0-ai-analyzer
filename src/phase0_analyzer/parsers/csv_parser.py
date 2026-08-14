"""CSV parser with the required Japanese encoding fallback order."""

import codecs
import csv
import io
from pathlib import Path

from phase0_analyzer.parsers.base import BaseParser
from phase0_analyzer.parsers.models import ParseError, ParseResult, ParseWarning


MAX_SOURCE_ROWS = 100
ENCODING_ORDER = ("utf-8", "utf-8-sig", "cp932", "shift_jis")


def _decode_csv(content: bytes) -> tuple[str, str]:
    for encoding in ENCODING_ORDER:
        if encoding == "utf-8" and content.startswith(codecs.BOM_UTF8):
            continue
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ParseError("CSV_DECODE_FAILED", "CSVの文字コードを判定できませんでした。")


class CsvParser(BaseParser):
    """Extract CSV structure and preserve non-fatal row warnings."""

    parser_name = "csv"
    supported_extensions = frozenset({"csv"})

    def __init__(self, preview_max_rows: int = 30) -> None:
        self.preview_max_rows = preview_max_rows

    def _parse(self, file_id: int, file_name: str, path: Path) -> ParseResult:
        try:
            content = path.read_bytes()
        except OSError as error:
            raise ParseError("CSV_READ_FAILED", "CSVファイルを読み取れませんでした。") from error

        text, encoding = _decode_csv(content)
        warnings: list[ParseWarning] = []
        try:
            delimiter = csv.Sniffer().sniff(text[:8192]).delimiter if text else ","
        except csv.Error:
            delimiter = ","
            warnings.append(
                ParseWarning(
                    code="CSV_DELIMITER_FALLBACK",
                    message="区切り文字を判定できないためカンマを使用しました。",
                )
            )

        try:
            rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
        except csv.Error as error:
            raise ParseError("CSV_PARSE_FAILED", "CSVの行を解析できませんでした。") from error

        column_count = max((len(row) for row in rows), default=0)
        inconsistent_rows = [
            index for index, row in enumerate(rows, start=1) if len(row) != column_count
        ]
        if inconsistent_rows:
            warnings.append(
                ParseWarning(
                    code="CSV_COLUMN_COUNT_MISMATCH",
                    message=f"列数が一致しない行があります: {inconsistent_rows[:10]}",
                )
            )

        source_rows = rows[:MAX_SOURCE_ROWS]
        table_preview = [
            {"row_number": index, "values": row}
            for index, row in enumerate(source_rows[: self.preview_max_rows], start=1)
        ]
        return ParseResult(
            file_id=file_id,
            file_name=file_name,
            file_type="csv",
            parser_name=self.parser_name,
            success=True,
            extracted_text=text,
            table_preview=table_preview,
            metadata={
                "encoding": encoding,
                "delimiter": delimiter,
                "row_count": len(rows),
                "column_count": column_count,
                "header_candidate": rows[0] if rows else [],
                "first_100_rows": source_rows,
            },
            warnings=warnings,
        )
