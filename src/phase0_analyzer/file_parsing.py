"""Parse the exact registered file selected by file ID."""

from pathlib import Path

from phase0_analyzer.file_discovery import calculate_sha256
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.parsers.models import ParseResult
from phase0_analyzer.parsers.resolver import ParserResolver


class FileParsingService:
    """Read a registered file version without creating analysis history."""

    def __init__(self, repository: FileRepository, resolver: ParserResolver) -> None:
        self.repository = repository
        self.resolver = resolver

    def parse(self, file_id: int) -> ParseResult:
        """Parse only the file record selected by ID."""
        stored_file = self.repository.get_by_id(file_id)
        if stored_file is None:
            return ParseResult(
                file_id=file_id,
                file_name="",
                file_type="",
                parser_name="resolver",
                success=False,
                error_code="FILE_ID_NOT_FOUND",
                error_message="指定されたファイルIDが見つかりません。",
            )

        path = Path(stored_file.original_snapshot_path or stored_file.source_path)
        if not path.is_file():
            return ParseResult(
                file_id=file_id,
                file_name=stored_file.file_name,
                file_type=stored_file.extension,
                parser_name="resolver",
                success=False,
                error_code="SOURCE_FILE_NOT_FOUND",
                error_message="解析対象の原本ファイルが見つかりません。",
            )

        try:
            current_sha256 = calculate_sha256(path)
        except OSError:
            return ParseResult(
                file_id=file_id,
                file_name=stored_file.file_name,
                file_type=stored_file.extension,
                parser_name="resolver",
                success=False,
                error_code="SOURCE_FILE_READ_FAILED",
                error_message="登録時の元ファイルを読み取れませんでした。",
            )
        if current_sha256 != stored_file.sha256:
            return ParseResult(
                file_id=file_id,
                file_name=stored_file.file_name,
                file_type=stored_file.extension,
                parser_name="resolver",
                success=False,
                error_code="FILE_VERSION_MISMATCH",
                error_message="登録後にファイル内容が変更されたため、この版は解析できません。",
            )

        parser = self.resolver.resolve(stored_file.extension)
        return parser.parse(file_id, stored_file.file_name, path)
