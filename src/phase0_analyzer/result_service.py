"""Read, correct, and confirm immutable AI analysis results."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phase0_analyzer.database import connect
from phase0_analyzer.file_repository import FileRepository


@dataclass(frozen=True, slots=True)
class RunSummary:
    id: int
    run_number: int
    completed_at: str | None
    status: str


@dataclass(frozen=True, slots=True)
class LatestResultSummary:
    file_id: int
    run_id: int
    run_number: int
    category_code: str | None
    document_type: str | None
    review_count: int


@dataclass(frozen=True, slots=True)
class ResultDetail:
    file: dict[str, Any]
    run: dict[str, Any]
    result: dict[str, Any]
    fields: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    current: dict[tuple[str, int | None], str | None]
    confirmation: dict[str, Any] | None
    review_count: int


class ResultService:
    def __init__(self, database_path: Path, files: FileRepository) -> None:
        self.database_path = database_path
        self.files = files

    def list_runs(self, file_id: int) -> list[RunSummary]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """SELECT id, run_number, completed_at, status FROM analysis_runs
                WHERE file_id = ? ORDER BY run_number DESC""",
                (file_id,),
            ).fetchall()
        return [RunSummary(*row) for row in rows]

    def latest_by_file(self) -> dict[int, LatestResultSummary]:
        """Return each file's latest successful analysis summary for the list UI."""
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                WITH ranked AS (
                    SELECT id, file_id, run_number,
                           ROW_NUMBER() OVER (
                               PARTITION BY file_id
                               ORDER BY COALESCE(run_number, 0) DESC, id DESC
                           ) AS position
                    FROM analysis_runs
                    WHERE status != 'FAILED'
                )
                SELECT
                    ranked.file_id,
                    ranked.id,
                    ranked.run_number,
                    result.category_code,
                    result.document_type,
                    (
                        SELECT COUNT(DISTINCT code) FROM warnings
                        WHERE analysis_run_id = ranked.id
                          AND severity IN ('warning', 'error')
                    ) AS warning_count,
                    (
                        SELECT COUNT(DISTINCT id) FROM extracted_fields
                        WHERE analysis_run_id = ranked.id AND needs_review = 1
                    ) AS field_count,
                    result.category_confidence,
                    result.document_type_confidence,
                    result.needs_review
                FROM ranked
                JOIN analysis_results AS result
                    ON result.analysis_run_id = ranked.id
                WHERE ranked.position = 1
                """
            ).fetchall()
        return {
            row[0]: LatestResultSummary(
                file_id=row[0],
                run_id=row[1],
                run_number=row[2],
                category_code=row[3],
                document_type=row[4],
                review_count=self._review_count(
                    category_code=row[3],
                    category_confidence=row[7],
                    document_type_confidence=row[8],
                    warning_count=row[5],
                    field_count=row[6],
                    result_needs_review=bool(row[9]),
                ),
            )
            for row in rows
        }

    def get_detail(self, run_id: int) -> ResultDetail:
        with connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            run = connection.execute(
                "SELECT * FROM analysis_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise ValueError("指定された分析runが見つかりません。")
            file = connection.execute(
                "SELECT * FROM files WHERE id = ?", (run["file_id"],)
            ).fetchone()
            result = connection.execute(
                "SELECT * FROM analysis_results WHERE analysis_run_id = ?", (run_id,)
            ).fetchone()
            if result is None:
                raise ValueError("このrunには表示できる分析結果がありません。")
            fields = connection.execute(
                "SELECT * FROM extracted_fields WHERE analysis_run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            warnings = connection.execute(
                "SELECT * FROM warnings WHERE analysis_run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
            corrections = connection.execute(
                """SELECT target_type, target_id, value_after FROM correction_history
                WHERE analysis_result_id = ? ORDER BY id""",
                (result["id"],),
            ).fetchall()
            confirmation = connection.execute(
                """SELECT * FROM confirmed_results WHERE analysis_result_id = ?
                ORDER BY id DESC LIMIT 1""",
                (result["id"],),
            ).fetchone()
        current = self._base_values(dict(result), [dict(row) for row in fields])
        for correction in corrections:
            current[(correction[0], correction[1])] = correction[2]
        result_dict = dict(result)
        field_dicts = [dict(row) for row in fields]
        warning_dicts = [dict(row) for row in warnings]
        review_count = self._review_count(
            category_code=result_dict["category_code"],
            category_confidence=result_dict["category_confidence"],
            document_type_confidence=result_dict["document_type_confidence"],
            warning_count=len(
                {
                    warning["code"]
                    for warning in warning_dicts
                    if warning["severity"] in {"warning", "error"}
                }
            ),
            field_count=sum(1 for field in field_dicts if field["needs_review"]),
            result_needs_review=bool(result_dict["needs_review"]),
        )
        return ResultDetail(
            file=dict(file),
            run=dict(run),
            result=result_dict,
            fields=field_dicts,
            warnings=warning_dicts,
            current=current,
            confirmation=dict(confirmation) if confirmation else None,
            review_count=review_count,
        )

    @staticmethod
    def _review_count(
        *,
        category_code: str,
        category_confidence: float,
        document_type_confidence: float,
        warning_count: int,
        field_count: int,
        result_needs_review: bool,
    ) -> int:
        category_issue = int(category_code == "UNKNOWN" or category_confidence < 0.80)
        document_issue = int(document_type_confidence < 0.70)
        count = warning_count + field_count + category_issue + document_issue
        return max(1, count) if result_needs_review else count

    @staticmethod
    def _base_values(result, fields) -> dict[tuple[str, int | None], str | None]:
        values = {
            ("category", None): result["category_code"],
            ("document_type", None): result["document_type"],
            ("provider_name", None): result["provider_name"],
            ("target_date", None): result["target_date"],
        }
        for field in fields:
            values[("field_value", field["id"])] = field["extracted_value"]
            values[("field_normalized_name", field["id"])] = field["normalized_name"]
        return values

    def save_corrections(
        self,
        run_id: int,
        changes: dict[tuple[str, int | None], str | None],
        corrected_by: str,
    ) -> int:
        detail = self.get_detail(run_id)
        changed = [(key, detail.current.get(key), value) for key, value in changes.items()
                   if detail.current.get(key) != value]
        if not changed:
            return 0
        with connect(self.database_path) as connection:
            connection.executemany(
                """INSERT INTO correction_history(
                    analysis_run_id, extracted_field_id, field_name, value_before,
                    value_after, corrected_by, file_id, analysis_result_id,
                    target_type, target_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(
                    run_id, key[1] if key[0].startswith("field_") else None,
                    key[0], before, after, corrected_by, detail.file["id"],
                    detail.result["id"], key[0], key[1],
                ) for key, before, after in changed],
            )
        return len(changed)

    def confirm(self, run_id: int, confirmed_by: str) -> int:
        detail = self.get_detail(run_id)
        final = {f"{key[0]}:{key[1]}": value for key, value in detail.current.items()}
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """INSERT INTO confirmed_results(
                    analysis_run_id, result_json, confirmed_by, file_id,
                    analysis_result_id, confirmed_category_code,
                    confirmed_document_type, confirmed_provider_name,
                    confirmed_target_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id, json.dumps(final, ensure_ascii=False), confirmed_by,
                    detail.file["id"], detail.result["id"],
                    detail.current[("category", None)],
                    detail.current[("document_type", None)],
                    detail.current[("provider_name", None)],
                    detail.current[("target_date", None)],
                ),
            )
            confirmed_id = int(cursor.lastrowid)
            connection.executemany(
                """INSERT INTO confirmed_fields(
                    confirmed_result_id, extracted_field_id, normalized_name, confirmed_value
                ) VALUES (?, ?, ?, ?)""",
                [(
                    confirmed_id, field["id"],
                    detail.current[("field_normalized_name", field["id"])],
                    detail.current[("field_value", field["id"])],
                ) for field in detail.fields],
            )
        self.files.update_status(detail.file["id"], "CONFIRMED")
        return confirmed_id
