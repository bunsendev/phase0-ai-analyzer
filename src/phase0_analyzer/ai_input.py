"""Build a bounded AI request input without mutating parser results."""

import json
from dataclasses import dataclass
from typing import Any

from phase0_analyzer.ai_models import AnalysisWarning
from phase0_analyzer.parsers.models import ParseResult


@dataclass(frozen=True, slots=True)
class PreparedAIInput:
    extracted_text: str
    table_preview: list[dict[str, Any]]
    parser_metadata: dict[str, Any]
    ocr_text: str
    warnings: list[AnalysisWarning]
    total_columns: int
    selected_columns: tuple[int, ...]
    input_character_count: int


def _source_rows(parsed: ParseResult) -> list[list[Any]]:
    if parsed.file_type == "xlsx":
        return [
            row
            for sheet in parsed.metadata.get("sheets", [])
            for row in sheet.get("first_100_rows", [])
        ]
    if parsed.file_type == "csv":
        return list(parsed.metadata.get("first_100_rows", []))
    return []


def _total_columns(parsed: ParseResult, rows: list[list[Any]]) -> int:
    if parsed.file_type == "xlsx":
        return max(
            (int(sheet.get("column_count", 0)) for sheet in parsed.metadata.get("sheets", [])),
            default=0,
        )
    if parsed.file_type == "csv":
        return int(parsed.metadata.get("column_count", 0))
    return max((len(row) for row in rows), default=0)


def _select_non_empty_columns(
    rows: list[list[Any]], total_columns: int, max_columns: int
) -> tuple[int, ...]:
    non_empty = [
        column
        for column in range(total_columns)
        if any(column < len(row) and row[column] not in (None, "") for row in rows)
    ]
    return tuple(non_empty[:max_columns])


def _limit_preview_columns(
    table_preview: list[dict[str, Any]], selected_columns: tuple[int, ...]
) -> list[dict[str, Any]]:
    limited: list[dict[str, Any]] = []
    for row in table_preview:
        copied = dict(row)
        values = copied.get("values")
        if isinstance(values, list):
            copied["values"] = [
                values[column] if column < len(values) else None
                for column in selected_columns
            ]
            copied["column_numbers"] = [column + 1 for column in selected_columns]
        limited.append(copied)
    return limited


def _limited_metadata(
    parsed: ParseResult,
    selected_columns: tuple[int, ...],
    total_columns: int,
) -> dict[str, Any]:
    if parsed.file_type == "xlsx":
        sheets = []
        for sheet in parsed.metadata.get("sheets", []):
            summary = {
                key: value
                for key, value in sheet.items()
                if key not in {"first_100_rows", "header_candidate"}
            }
            header = sheet.get("header_candidate", [])
            summary["header_candidate"] = [
                header[column] if column < len(header) else None
                for column in selected_columns
            ]
            sheets.append(summary)
        metadata: dict[str, Any] = {
            "sheet_names": list(parsed.metadata.get("sheet_names", [])),
            "sheets": sheets,
        }
    elif parsed.file_type == "csv":
        metadata = {
            key: value
            for key, value in parsed.metadata.items()
            if key not in {"first_100_rows", "header_candidate"}
        }
        header = parsed.metadata.get("header_candidate", [])
        metadata["header_candidate"] = [
            header[column] if column < len(header) else None
            for column in selected_columns
        ]
    else:
        metadata = dict(parsed.metadata)
    metadata["ai_input"] = {
        "total_columns": total_columns,
        "selected_column_numbers": [column + 1 for column in selected_columns],
    }
    return metadata


def prepare_ai_input(
    parsed: ParseResult,
    ocr_text: str,
    *,
    max_columns: int,
    max_characters: int,
) -> PreparedAIInput:
    """Return bounded AI fields while leaving ``parsed`` untouched."""
    rows = _source_rows(parsed)
    total_columns = _total_columns(parsed, rows)
    selected_columns = _select_non_empty_columns(rows, total_columns, max_columns)
    preview_by_columns = _limit_preview_columns(parsed.table_preview, selected_columns)

    if rows and parsed.file_type in {"xlsx", "csv"}:
        source_text = "\n".join(
            str(row[column])
            for row in rows
            for column in selected_columns
            if column < len(row) and row[column] not in (None, "")
        )
    else:
        source_text = parsed.extracted_text

    ocr_limit = max(0, max_characters - 4)
    limited_ocr = ocr_text[:ocr_limit]
    preview: list[dict[str, Any]] = []
    for row in preview_by_columns:
        candidate = [*preview, row]
        candidate_size = len(json.dumps(candidate, ensure_ascii=False, default=str))
        if len(limited_ocr) + candidate_size + 2 > max_characters:
            break
        preview = candidate

    preview_size = len(json.dumps(preview, ensure_ascii=False, default=str))
    remaining = max(0, max_characters - len(limited_ocr) - preview_size - 2)
    limited_text = source_text[:remaining]
    input_character_count = len(limited_text) + len(limited_ocr) + preview_size + 2

    columns_truncated = total_columns > len(selected_columns)
    characters_truncated = (
        limited_text != source_text
        or limited_ocr != ocr_text
        or len(preview) != len(preview_by_columns)
    )
    warnings = []
    if columns_truncated or characters_truncated:
        warnings.append(
            AnalysisWarning(
                code="AI_INPUT_TRUNCATED",
                severity="warning",
                message=(
                    "AI入力を安全上限に合わせて切り詰めました。"
                    f"列数: {len(selected_columns)}/{total_columns}、"
                    f"入力文字数: {input_character_count}/{max_characters}。"
                ),
            )
        )

    return PreparedAIInput(
        extracted_text=limited_text,
        table_preview=preview,
        parser_metadata=_limited_metadata(parsed, selected_columns, total_columns),
        ocr_text=limited_ocr,
        warnings=warnings,
        total_columns=total_columns,
        selected_columns=selected_columns,
        input_character_count=input_character_count,
    )
