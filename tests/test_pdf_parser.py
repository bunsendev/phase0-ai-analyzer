from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from phase0_analyzer.parsers.pdf import PdfParser


def create_text_pdf(path: Path, pages: int = 1) -> None:
    document = canvas.Canvas(str(path))
    for page in range(pages):
        document.drawString(72, 720, f"Order document page {page + 1} with enough text")
        document.showPage()
    document.save()


def test_text_pdf_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "text.pdf"
    create_text_pdf(path)

    result = PdfParser(text_threshold=10, max_pages=10).parse(1, path.name, path)

    assert result.success
    assert result.requires_ocr is False
    assert result.metadata["pdf_type"] == "text"
    assert result.metadata["page_count"] == 1
    assert result.metadata["extracted_character_count"] >= 10


def test_image_pdf_requires_ocr(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    Image.new("RGB", (800, 800), "white").save(image_path)
    path = tmp_path / "image.pdf"
    document = canvas.Canvas(str(path))
    document.drawImage(ImageReader(str(image_path)), 0, 0, width=500, height=500)
    document.showPage()
    document.save()

    result = PdfParser(text_threshold=10, max_pages=10).parse(2, path.name, path)

    assert result.success
    assert result.requires_ocr is True
    assert result.metadata["pdf_type"] == "image"
    assert result.extracted_text.strip() == ""


def test_pdf_page_limit_is_warning_not_failure(tmp_path: Path) -> None:
    path = tmp_path / "long.pdf"
    create_text_pdf(path, pages=3)

    result = PdfParser(text_threshold=1, max_pages=2).parse(3, path.name, path)

    assert result.success
    assert result.metadata["page_count"] == 3
    assert result.metadata["parsed_page_count"] == 2
    assert "PDF_PAGE_LIMIT_EXCEEDED" in {warning.code for warning in result.warnings}
