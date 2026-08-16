from copy import deepcopy

from phase0_analyzer.ai_input import prepare_ai_input
from phase0_analyzer.parsers.models import ParseResult


def make_excel_result() -> ParseResult:
    rows = [
        [None, "B1", "C1", "D1"],
        [None, "B2", None, "D2"],
    ]
    return ParseResult(
        file_id=1,
        file_name="wide.xlsx",
        file_type="xlsx",
        parser_name="excel",
        success=True,
        extracted_text="original parser text",
        table_preview=[
            {"sheet_name": "Sheet1", "row_number": index, "values": row}
            for index, row in enumerate(rows, start=1)
        ],
        metadata={
            "sheet_names": ["Sheet1"],
            "sheets": [
                {
                    "sheet_name": "Sheet1",
                    "row_count": 2,
                    "column_count": 4,
                    "header_candidate": rows[0],
                    "first_100_rows": rows,
                    "has_formulas": False,
                    "has_merged_cells": False,
                    "empty_row_count": 0,
                    "empty_column_count": 1,
                }
            ],
        },
    )


def test_ai_input_prioritizes_non_empty_columns_in_source_order() -> None:
    parsed = make_excel_result()

    prepared = prepare_ai_input(
        parsed, "", max_columns=2, max_characters=10_000
    )

    assert prepared.total_columns == 4
    assert prepared.selected_columns == (1, 2)
    assert prepared.table_preview[0]["values"] == ["B1", "C1"]
    assert prepared.table_preview[0]["column_numbers"] == [2, 3]
    assert any(warning.code == "AI_INPUT_TRUNCATED" for warning in prepared.warnings)


def test_ai_input_respects_character_limit_and_preserves_parser_result() -> None:
    parsed = make_excel_result()
    original_preview = deepcopy(parsed.table_preview)
    original_metadata = deepcopy(parsed.metadata)

    prepared = prepare_ai_input(
        parsed, "OCR" * 100, max_columns=4, max_characters=80
    )

    assert prepared.input_character_count <= 80
    assert any(warning.code == "AI_INPUT_TRUNCATED" for warning in prepared.warnings)
    assert parsed.extracted_text == "original parser text"
    assert parsed.table_preview == original_preview
    assert parsed.metadata == original_metadata
    assert len(parsed.metadata["sheets"][0]["first_100_rows"][0]) == 4
