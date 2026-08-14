"""Small extension-to-parser resolver."""

from pathlib import Path

from phase0_analyzer.config import Settings
from phase0_analyzer.parsers.base import BaseParser
from phase0_analyzer.parsers.csv_parser import CsvParser
from phase0_analyzer.parsers.excel import ExcelParser
from phase0_analyzer.parsers.image import ImageParser
from phase0_analyzer.parsers.models import ParseResult
from phase0_analyzer.parsers.pdf import PdfParser


class UnsupportedParser(BaseParser):
    """Return an explicit result for formats outside the prototype scope."""

    parser_name = "unsupported"

    def _parse(self, file_id: int, file_name: str, path: Path) -> ParseResult:
        return self.failure_result(
            file_id=file_id,
            file_name=file_name,
            file_type=path.suffix.lower().removeprefix("."),
            error_code="UNSUPPORTED_FILE_TYPE",
            error_message="このファイル形式には対応していません。",
        )


class ParserResolver:
    """Resolve the parser configured for a registered extension."""

    def __init__(self, settings: Settings) -> None:
        excel = ExcelParser(settings.table_preview_max_rows)
        csv_parser = CsvParser(settings.table_preview_max_rows)
        image = ImageParser()
        self._parsers: dict[str, BaseParser] = {
            "xlsx": excel,
            "csv": csv_parser,
            "pdf": PdfParser(settings.pdf_text_threshold, settings.pdf_max_pages),
            "png": image,
            "jpg": image,
            "jpeg": image,
        }
        self._unsupported = UnsupportedParser()

    def resolve(self, extension: str) -> BaseParser:
        """Return a parser or an explicit unsupported parser."""
        return self._parsers.get(extension.lower().removeprefix("."), self._unsupported)
