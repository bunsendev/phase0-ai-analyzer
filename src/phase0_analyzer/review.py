"""Central Day 4 review-required decision."""

from phase0_analyzer.ai_models import AIAnalysisResult, AnalysisWarning


def needs_review(
    result: AIAnalysisResult,
    warnings: list[AnalysisWarning],
    requires_ocr: bool,
    ocr_text: str,
    category_threshold: float,
    document_type_threshold: float,
) -> bool:
    return any(
        (
            result.needs_review,
            result.document_category.confidence < category_threshold,
            result.document_type.confidence < document_type_threshold,
            any(field.needs_review for field in result.fields),
            result.document_category.code == "UNKNOWN",
            any(warning.severity == "error" for warning in warnings),
            any(warning.code == "OCR_REVIEW_REQUIRED" for warning in warnings),
            requires_ocr and not ocr_text.strip(),
        )
    )
