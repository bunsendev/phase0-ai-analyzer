from phase0_analyzer.ai_models import (
    AIAnalysisResult,
    AnalysisWarning,
    ConfidenceValue,
    DocumentCategory,
    DocumentType,
    ExtractedField,
)
from phase0_analyzer.review import needs_review


def make_result(**changes) -> AIAnalysisResult:
    values = {
        "document_category": DocumentCategory(
            code="ORDER", label="受注", confidence=0.95, reason="test"
        ),
        "document_type": DocumentType(name="受注票", confidence=0.90),
        "provider_name": ConfidenceValue(value="test", confidence=0.9),
        "target_date": ConfidenceValue(value=None, confidence=0.5),
        "summary": "test",
    }
    values.update(changes)
    return AIAnalysisResult(**values)


def evaluate(result, warnings=None, requires_ocr=False, ocr_text="") -> bool:
    return needs_review(result, warnings or [], requires_ocr, ocr_text, 0.8, 0.7)


def test_review_conditions() -> None:
    assert not evaluate(make_result())
    assert evaluate(
        make_result(
            document_category=DocumentCategory(
                code="ORDER", label="受注", confidence=0.79, reason="low"
            )
        )
    )
    assert evaluate(
        make_result(
            document_category=DocumentCategory(
                code="UNKNOWN", label="不明", confidence=0.9, reason="unknown"
            )
        )
    )
    assert evaluate(
        make_result(
            fields=[
                ExtractedField(
                    source_name="x", normalized_name="x", data_type="string",
                    confidence=0.9, needs_review=True
                )
            ]
        )
    )
    assert evaluate(
        make_result(),
        [AnalysisWarning(code="E", severity="error", message="error")],
    )
    assert evaluate(make_result(), requires_ocr=True, ocr_text="")
