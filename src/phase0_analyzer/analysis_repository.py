"""Append-only persistence for Day 4 analysis history."""

from dataclasses import dataclass
from datetime import datetime

from phase0_analyzer.ai_models import AIAnalysisResult, AnalysisWarning
from phase0_analyzer.database import connect


@dataclass(frozen=True, slots=True)
class SavedRun:
    id: int
    run_number: int


class AnalysisRepository:
    def __init__(self, database_path) -> None:
        self.database_path = database_path

    def _next_run_number(self, connection, file_id: int) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(run_number), 0) + 1 FROM analysis_runs WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        return int(row[0])

    def save_success(
        self,
        *,
        file_id: int,
        status: str,
        provider: str,
        model_name: str,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: int,
        extracted_text: str,
        raw_ai_response: str,
        result: AIAnalysisResult,
        warnings: list[AnalysisWarning],
    ) -> SavedRun:
        """Save one complete run and all children in one transaction."""
        with connect(self.database_path) as connection:
            run_number = self._next_run_number(connection, file_id)
            cursor = connection.execute(
                """
                INSERT INTO analysis_runs(
                    file_id, run_number, status, started_at, completed_at,
                    duration_ms, provider, model_name, extracted_text,
                    raw_ai_response
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    run_number,
                    status,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    duration_ms,
                    provider,
                    model_name,
                    extracted_text,
                    raw_ai_response,
                ),
            )
            run_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO analysis_results(
                    analysis_run_id, category_code, category_label,
                    category_confidence, category_reason, document_type,
                    document_type_confidence, provider_name, target_date,
                    summary, needs_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    result.document_category.code,
                    result.document_category.label,
                    result.document_category.confidence,
                    result.document_category.reason,
                    result.document_type.name,
                    result.document_type.confidence,
                    result.provider_name.value,
                    result.target_date.value,
                    result.summary,
                    int(status == "REVIEW_REQUIRED"),
                ),
            )
            connection.executemany(
                """
                INSERT INTO extracted_fields(
                    analysis_run_id, source_name, common_name, normalized_name,
                    extracted_value, corrected_value, data_type, confidence,
                    requires_review, needs_review, review_reason
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        field.source_name,
                        field.normalized_name,
                        field.normalized_name,
                        field.value,
                        field.data_type,
                        field.confidence,
                        int(field.needs_review),
                        int(field.needs_review),
                        field.review_reason,
                    )
                    for field in result.fields
                ],
            )
            connection.executemany(
                """
                INSERT INTO warnings(analysis_run_id, severity, code, message)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (run_id, warning.severity, warning.code, warning.message)
                    for warning in warnings
                ],
            )
        return SavedRun(run_id, run_number)

    def save_failure(
        self,
        *,
        file_id: int,
        provider: str,
        model_name: str,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: int,
        error_code: str,
        error_message: str,
    ) -> SavedRun:
        with connect(self.database_path) as connection:
            run_number = self._next_run_number(connection, file_id)
            cursor = connection.execute(
                """
                INSERT INTO analysis_runs(
                    file_id, run_number, status, started_at, completed_at,
                    duration_ms, provider, model_name, error_code, error_message
                ) VALUES (?, ?, 'FAILED', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    run_number,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    duration_ms,
                    provider,
                    model_name,
                    error_code,
                    error_message,
                ),
            )
            return SavedRun(int(cursor.lastrowid), run_number)
