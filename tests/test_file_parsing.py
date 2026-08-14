import sqlite3
from pathlib import Path

from phase0_analyzer.config import Settings
from phase0_analyzer.database import initialize_database
from phase0_analyzer.file_discovery import discover_files
from phase0_analyzer.file_parsing import FileParsingService
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.parsers.csv_parser import CsvParser
from phase0_analyzer.parsers.excel import ExcelParser
from phase0_analyzer.parsers.image import ImageParser
from phase0_analyzer.parsers.pdf import PdfParser
from phase0_analyzer.parsers.resolver import ParserResolver, UnsupportedParser


def create_service(tmp_path: Path) -> tuple[FileRepository, FileParsingService]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'parse.db'}", _env_file=None
    )
    initialize_database(settings)
    repository = FileRepository(settings.database_path)
    return repository, FileParsingService(repository, ParserResolver(settings))


def test_resolver_selects_parser_by_extension(tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    resolver = ParserResolver(settings)

    assert isinstance(resolver.resolve("xlsx"), ExcelParser)
    assert isinstance(resolver.resolve(".CSV"), CsvParser)
    assert isinstance(resolver.resolve("pdf"), PdfParser)
    assert isinstance(resolver.resolve("png"), ImageParser)
    assert isinstance(resolver.resolve("jpg"), ImageParser)
    assert isinstance(resolver.resolve("jpeg"), ImageParser)
    assert isinstance(resolver.resolve("txt"), UnsupportedParser)


def test_unsupported_registered_file_returns_explicit_result(tmp_path: Path) -> None:
    source_dir = tmp_path / "upload"
    source_dir.mkdir()
    path = source_dir / "memo.txt"
    path.write_text("memo", encoding="utf-8")
    repository, service = create_service(tmp_path)
    repository.register(discover_files(source_dir)[0])
    file_id = repository.list_all()[0].id

    result = service.parse(file_id)

    assert not result.success
    assert result.error_code == "UNSUPPORTED_FILE_TYPE"


def test_service_parses_the_record_selected_by_file_id(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    (first_dir / "orders.csv").write_text("id,value\nold,100", encoding="utf-8")
    (second_dir / "orders.csv").write_text("id,value\nnew,200", encoding="utf-8")
    repository, service = create_service(tmp_path)
    repository.register(discover_files(first_dir)[0])
    repository.register(discover_files(second_dir)[0])
    files_by_path = {Path(file.source_path).parent.name: file for file in repository.list_all()}

    result = service.parse(files_by_path["first"].id)

    assert result.success
    assert result.file_id == files_by_path["first"].id
    assert "old,100" in result.extracted_text
    assert "new,200" not in result.extracted_text


def test_changed_registered_version_is_not_silently_parsed(tmp_path: Path) -> None:
    source_dir = tmp_path / "upload"
    source_dir.mkdir()
    path = source_dir / "orders.csv"
    path.write_text("id,value\nold,100", encoding="utf-8")
    repository, service = create_service(tmp_path)
    repository.register(discover_files(source_dir)[0])
    file_id = repository.list_all()[0].id
    path.write_text("id,value\nnew,200", encoding="utf-8")

    result = service.parse(file_id)

    assert not result.success
    assert result.error_code == "FILE_VERSION_MISMATCH"


def test_parsing_does_not_create_analysis_run(tmp_path: Path) -> None:
    source_dir = tmp_path / "upload"
    source_dir.mkdir()
    (source_dir / "inventory.csv").write_text("item,count\nA,1", encoding="utf-8")
    repository, service = create_service(tmp_path)
    repository.register(discover_files(source_dir)[0])
    file_id = repository.list_all()[0].id

    result = service.parse(file_id)

    assert result.success
    with sqlite3.connect(repository.database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()
    assert count == (0,)
