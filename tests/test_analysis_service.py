import sqlite3
from pathlib import Path

from PIL import Image

from phase0_analyzer.ai_provider import MockAIProvider
from phase0_analyzer.analysis_repository import AnalysisRepository
from phase0_analyzer.analysis_service import AnalysisService
from phase0_analyzer.config import Settings
from phase0_analyzer.database import initialize_database
from phase0_analyzer.file_discovery import discover_files
from phase0_analyzer.file_parsing import FileParsingService
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.ocr_provider import MockOCRProvider, OCRRequest, OCRResult
from phase0_analyzer.parsers.models import ParseWarning
from phase0_analyzer.parsers.resolver import ParserResolver
from phase0_analyzer.snapshot import SnapshotService


class FailedOCRProvider:
    provider_name = "failed-ocr"

    def extract_text(self, request: OCRRequest) -> OCRResult:
        return OCRResult(
            success=False,
            warnings=[ParseWarning(code="OCR_EMPTY", message="OCR結果なし", level="error")],
            error_code="OCR_FAILED",
            error_message="OCRに失敗しました。",
        )


def build_service(
    tmp_path: Path, file_name: str, content: bytes, ocr=None, **setting_values
):
    upload = tmp_path / "upload"
    upload.mkdir()
    path = upload / file_name
    path.write_bytes(content)
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'analysis.db'}",
        original_dir=tmp_path / "original",
        _env_file=None,
        **setting_values,
    )
    initialize_database(settings)
    files = FileRepository(settings.database_path)
    snapshots = SnapshotService(tmp_path / "original")
    snapshots.register(discover_files(upload)[0], files)
    service = AnalysisService(
        settings=settings,
        files=files,
        parsing=FileParsingService(files, ParserResolver(settings)),
        snapshots=snapshots,
        ocr=ocr or MockOCRProvider(),
        ai=MockAIProvider(),
        analyses=AnalysisRepository(settings.database_path),
    )
    return service, files, files.list_all()[0].id


def test_analysis_saves_append_only_history_and_children(tmp_path: Path) -> None:
    service, files, file_id = build_service(
        tmp_path, "orders.csv", "受注番号,金額\nA1,100".encode("utf-8")
    )

    first = service.analyze(file_id)
    second = service.analyze(file_id)

    assert first.run_number == 1
    assert second.run_number == 2
    assert first.status == "COMPLETED"
    with sqlite3.connect(files.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM analysis_results").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM extracted_fields").fetchone() == (2,)
        runs = connection.execute(
            "SELECT run_number FROM analysis_runs ORDER BY run_number"
        ).fetchall()
    assert runs == [(1,), (2,)]


def test_ocr_is_not_called_when_not_required(tmp_path: Path) -> None:
    ocr = MockOCRProvider()
    service, _, file_id = build_service(
        tmp_path, "orders.csv", "受注番号\nA1".encode("utf-8"), ocr
    )

    service.analyze(file_id)

    assert ocr.call_count == 0


def test_mock_ocr_is_called_for_image(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    Image.new("RGB", (600, 600), "white").save(image_path)
    ocr = MockOCRProvider(text="配送 送り状")
    service, _, file_id = build_service(tmp_path, "shipping.png", image_path.read_bytes(), ocr)

    outcome = service.analyze(file_id)

    assert ocr.call_count == 1
    assert outcome.status == "REVIEW_REQUIRED"
    assert outcome.result is not None
    assert outcome.result.document_category.code == "SHIPPING"


def test_image_review_rule_can_be_disabled(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    Image.new("RGB", (600, 600), "white").save(image_path)
    service, files, file_id = build_service(
        tmp_path,
        "shipping.png",
        image_path.read_bytes(),
        MockOCRProvider(text="配送 送り状"),
        ocr_review_required=False,
    )

    outcome = service.analyze(file_id)

    assert outcome.status == "COMPLETED"
    with sqlite3.connect(files.database_path) as connection:
        codes = connection.execute("SELECT code FROM warnings").fetchall()
    assert ("OCR_REVIEW_REQUIRED",) not in codes


def test_ai_input_truncation_warning_is_saved(tmp_path: Path) -> None:
    service, files, file_id = build_service(
        tmp_path,
        "wide.csv",
        "A,B,C,D\n1,2,3,4".encode("utf-8"),
        ai_max_columns=2,
        ai_max_input_chars=100,
    )

    outcome = service.analyze(file_id)

    assert outcome.status == "COMPLETED"
    with sqlite3.connect(files.database_path) as connection:
        codes = connection.execute("SELECT code FROM warnings").fetchall()
        saved_text = connection.execute(
            "SELECT extracted_text FROM analysis_runs"
        ).fetchone()[0]
    assert ("AI_INPUT_TRUNCATED",) in codes
    assert "A,B,C,D" in saved_text


def test_ocr_failure_becomes_review_required_and_warning(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    Image.new("RGB", (600, 600), "white").save(image_path)
    service, files, file_id = build_service(
        tmp_path, "unknown.png", image_path.read_bytes(), FailedOCRProvider()
    )

    outcome = service.analyze(file_id)

    assert outcome.status == "REVIEW_REQUIRED"
    with sqlite3.connect(files.database_path) as connection:
        severities = connection.execute("SELECT severity FROM warnings").fetchall()
    assert ("error",) in severities
