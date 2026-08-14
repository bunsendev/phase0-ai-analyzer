"""OCR provider boundary for later implementation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from phase0_analyzer.parsers.models import ParseWarning


@dataclass(frozen=True, slots=True)
class OCRRequest:
    """Input identifying a registered file for OCR."""

    file_id: int
    file_path: Path
    file_type: str


@dataclass(frozen=True, slots=True)
class OCRResult:
    """Provider-independent OCR output."""

    success: bool
    text: str = ""
    warnings: list[ParseWarning] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class OCRProvider(Protocol):
    """Interface implemented by a future OCR provider."""

    def extract_text(self, request: OCRRequest) -> OCRResult:
        """Extract text from an image or image-based PDF."""
        ...


class MockOCRProvider:
    """Deterministic OCR used only to complete the prototype flow."""

    provider_name = "mock-ocr"

    def __init__(self, text: str = "Mock OCRで抽出した帳票テキスト") -> None:
        self.text = text
        self.call_count = 0

    def extract_text(self, request: OCRRequest) -> OCRResult:
        self.call_count += 1
        return OCRResult(success=True, text=self.text)
