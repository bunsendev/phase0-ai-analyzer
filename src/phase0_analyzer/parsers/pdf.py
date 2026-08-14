"""PDF text extraction without OCR execution."""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from phase0_analyzer.parsers.base import BaseParser
from phase0_analyzer.parsers.models import ParseError, ParseResult, ParseWarning


class PdfParser(BaseParser):
    """Extract text from a bounded number of PDF pages."""

    parser_name = "pdf"
    supported_extensions = frozenset({"pdf"})

    def __init__(self, text_threshold: int = 50, max_pages: int = 10) -> None:
        self.text_threshold = text_threshold
        self.max_pages = max_pages

    def _parse(self, file_id: int, file_name: str, path: Path) -> ParseResult:
        try:
            reader = PdfReader(path)
            page_count = len(reader.pages)
            parsed_page_count = min(page_count, self.max_pages)
            page_texts = [
                reader.pages[index].extract_text() or ""
                for index in range(parsed_page_count)
            ]
        except (PdfReadError, OSError, ValueError) as error:
            raise ParseError("PDF_READ_FAILED", "PDFファイルを読み取れませんでした。") from error

        extracted_text = "\n".join(page_texts)
        extracted_character_count = len(extracted_text.strip())
        requires_ocr = extracted_character_count < self.text_threshold
        warnings: list[ParseWarning] = []
        if page_count > self.max_pages:
            warnings.append(
                ParseWarning(
                    code="PDF_PAGE_LIMIT_EXCEEDED",
                    message=(
                        f"PDFは{page_count}ページあります。"
                        f"先頭{self.max_pages}ページだけを解析しました。"
                    ),
                )
            )

        return ParseResult(
            file_id=file_id,
            file_name=file_name,
            file_type="pdf",
            parser_name=self.parser_name,
            success=True,
            extracted_text=extracted_text,
            metadata={
                "page_count": page_count,
                "parsed_page_count": parsed_page_count,
                "extracted_character_count": extracted_character_count,
                "pdf_type": "image" if requires_ocr else "text",
            },
            warnings=warnings,
            requires_ocr=requires_ocr,
        )
