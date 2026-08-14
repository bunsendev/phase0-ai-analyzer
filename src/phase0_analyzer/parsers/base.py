"""Base class for safe format-specific parsing."""

from abc import ABC, abstractmethod
from pathlib import Path

from phase0_analyzer.parsers.models import ParseError, ParseResult


class BaseParser(ABC):
    """Convert parser errors into a common failure result."""

    parser_name = "base"
    supported_extensions: frozenset[str] = frozenset()

    def parse(self, file_id: int, file_name: str, path: Path) -> ParseResult:
        """Parse without allowing a bad file to stop the application."""
        file_type = path.suffix.lower().removeprefix(".")
        try:
            return self._parse(file_id, file_name, path)
        except ParseError as error:
            return self.failure_result(
                file_id, file_name, file_type, error.code, error.message
            )
        except Exception:
            return self.failure_result(
                file_id,
                file_name,
                file_type,
                "UNEXPECTED_PARSE_ERROR",
                "ファイル解析中に予期しないエラーが発生しました。",
            )

    @abstractmethod
    def _parse(self, file_id: int, file_name: str, path: Path) -> ParseResult:
        """Implement format-specific parsing."""

    def failure_result(
        self,
        file_id: int,
        file_name: str,
        file_type: str,
        error_code: str,
        error_message: str,
    ) -> ParseResult:
        """Build a consistent failure result."""
        return ParseResult(
            file_id=file_id,
            file_name=file_name,
            file_type=file_type,
            parser_name=self.parser_name,
            success=False,
            error_code=error_code,
            error_message=error_message,
        )
