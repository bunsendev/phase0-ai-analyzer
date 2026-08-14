import pytest

from phase0_analyzer.ai_models import AnalysisRequest
from phase0_analyzer.ai_provider import MockAIProvider


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("受注一覧", "ORDER"),
        ("棚卸と在庫", "INVENTORY"),
        ("配送送り状", "SHIPPING"),
        ("社内メモ", "OTHER"),
        ("", "UNKNOWN"),
    ],
)
def test_mock_ai_returns_all_categories(text: str, expected: str) -> None:
    request = AnalysisRequest(
        file_id=1,
        file_name="sample.csv",
        file_type="csv",
        extracted_text=text,
    )

    result = MockAIProvider().analyze(request)

    assert result.document_category.code == expected
    assert result.model_dump()["document_category"]["confidence"] >= 0
