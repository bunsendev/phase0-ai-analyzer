import sqlite3
from pathlib import Path

from phase0_analyzer.ai_provider import MockAIProvider
from phase0_analyzer.analysis_repository import AnalysisRepository
from phase0_analyzer.analysis_service import AnalysisService
from phase0_analyzer.config import Settings
from phase0_analyzer.database import initialize_database
from phase0_analyzer.file_discovery import discover_files
from phase0_analyzer.file_parsing import FileParsingService
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.ocr_provider import MockOCRProvider
from phase0_analyzer.parsers.resolver import ParserResolver
from phase0_analyzer.result_service import ResultService
from phase0_analyzer.snapshot import SnapshotService


def setup_analyzed_file(tmp_path: Path):
    upload = tmp_path / "upload"
    upload.mkdir()
    (upload / "orders.csv").write_text("受注番号,金額\nA1,100", encoding="utf-8")
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'result.db'}",
        original_dir=tmp_path / "original",
        _env_file=None,
    )
    initialize_database(settings)
    files = FileRepository(settings.database_path)
    snapshots = SnapshotService(tmp_path / "original")
    snapshots.register(discover_files(upload)[0], files)
    file_id = files.list_all()[0].id
    analysis = AnalysisService(
        settings=settings,
        files=files,
        parsing=FileParsingService(files, ParserResolver(settings)),
        snapshots=snapshots,
        ocr=MockOCRProvider(),
        ai=MockAIProvider(),
        analyses=AnalysisRepository(settings.database_path),
    )
    outcome = analysis.analyze(file_id)
    return settings, files, analysis, ResultService(settings.database_path, files), file_id, outcome


def test_corrections_are_append_only_and_current_uses_latest(tmp_path: Path) -> None:
    settings, _, _, results, _, outcome = setup_analyzed_file(tmp_path)
    detail = results.get_detail(outcome.run_id)
    field_id = detail.fields[0]["id"]

    assert detail.current[("category", None)] == "ORDER"
    assert results.save_corrections(
        outcome.run_id,
        {
            ("category", None): "SHIPPING",
            ("document_type", None): "配送票",
            ("field_value", field_id): "修正1",
            ("field_normalized_name", field_id): "修正項目",
        },
        "tester",
    ) == 4
    assert results.save_corrections(
        outcome.run_id, {("field_value", field_id): "修正2"}, "tester"
    ) == 1
    updated = results.get_detail(outcome.run_id)
    assert updated.current[("category", None)] == "SHIPPING"
    assert updated.current[("field_value", field_id)] == "修正2"
    assert results.save_corrections(
        outcome.run_id, {("field_value", field_id): "修正2"}, "tester"
    ) == 0

    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM correction_history").fetchone() == (5,)
        original = connection.execute(
            "SELECT category_code FROM analysis_results WHERE id = ?",
            (detail.result["id"],),
        ).fetchone()
        extracted = connection.execute(
            "SELECT extracted_value FROM extracted_fields WHERE id = ?", (field_id,)
        ).fetchone()
    assert original == ("ORDER",)
    assert extracted[0] != "修正2"


def test_confirm_without_and_with_corrections_preserves_ai(tmp_path: Path) -> None:
    settings, files, _, results, file_id, outcome = setup_analyzed_file(tmp_path)
    first_confirmation = results.confirm(outcome.run_id, "tester")
    assert first_confirmation > 0
    results.save_corrections(
        outcome.run_id, {("category", None): "INVENTORY"}, "tester"
    )
    second_confirmation = results.confirm(outcome.run_id, "tester")

    assert second_confirmation > first_confirmation
    assert files.get_by_id(file_id).status == "CONFIRMED"
    with sqlite3.connect(settings.database_path) as connection:
        confirmations = connection.execute(
            "SELECT confirmed_category_code FROM confirmed_results ORDER BY id"
        ).fetchall()
        original = connection.execute("SELECT category_code FROM analysis_results").fetchone()
    assert confirmations == [("ORDER",), ("INVENTORY",)]
    assert original == ("ORDER",)


def test_confirmed_file_reanalysis_keeps_old_confirmation(tmp_path: Path) -> None:
    settings, _, analysis, results, file_id, outcome = setup_analyzed_file(tmp_path)
    results.confirm(outcome.run_id, "tester")

    new_outcome = analysis.analyze(file_id)

    assert new_outcome.run_number == 2
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM confirmed_results").fetchone() == (1,)
    assert results.list_runs(file_id)[0].run_number == 2


def test_latest_result_summary_uses_latest_run(tmp_path: Path) -> None:
    _, _, analysis, results, file_id, first = setup_analyzed_file(tmp_path)
    second = analysis.analyze(file_id)

    latest = results.latest_by_file()[file_id]

    assert latest.run_id == second.run_id
    assert latest.run_id != first.run_id
    assert latest.run_number == 2
    assert latest.category_code == "ORDER"
    assert latest.document_type == "受注票"
    assert latest.review_count == 0


def test_review_count_deduplicates_same_warning_code(tmp_path: Path) -> None:
    settings, _, _, results, file_id, outcome = setup_analyzed_file(tmp_path)
    with sqlite3.connect(settings.database_path) as connection:
        connection.executemany(
            """INSERT INTO warnings(analysis_run_id, severity, code, message)
            VALUES (?, 'warning', 'SAME_REASON', ?)""",
            [
                (outcome.run_id, "同じ理由です。"),
                (outcome.run_id, "同じ理由です。"),
            ],
        )

    assert results.latest_by_file()[file_id].review_count == 1
    assert results.get_detail(outcome.run_id).review_count == 1
