"""Common parser result models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ParseWarning:
    """A non-fatal condition found while parsing."""

    code: str
    message: str
    level: str = "warning"


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Format-independent result passed to later OCR and AI stages."""

    file_id: int
    file_name: str
    file_type: str
    parser_name: str
    success: bool
    extracted_text: str = ""
    table_preview: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[ParseWarning] = field(default_factory=list)
    requires_ocr: bool = False
    error_code: str | None = None
    error_message: str | None = None


class ParseError(RuntimeError):
    """An expected parser failure with a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
