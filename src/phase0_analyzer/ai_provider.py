"""AI provider interface and deterministic mock implementation."""

import json
from typing import Protocol

from phase0_analyzer.ai_models import (
    AIAnalysisResult,
    AnalysisRequest,
    ConfidenceValue,
    DocumentCategory,
    DocumentType,
    ExtractedField,
)


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def analyze(self, request: AnalysisRequest) -> AIAnalysisResult:
        ...


class MockAIProvider:
    """Keyword rules exercising the same contract as a future real AI."""

    provider_name = "mock"
    model_name = "mock-rules-v1"

    _rules = (
        ("ORDER", "受注・依頼", ("受注", "注文", "order")),
        ("INVENTORY", "在庫", ("在庫", "棚卸", "inventory", "stock")),
        ("SHIPPING", "出荷・配送", ("出荷", "配送", "送り状", "shipping")),
    )

    def analyze(self, request: AnalysisRequest) -> AIAnalysisResult:
        preview_text = json.dumps(request.table_preview, ensure_ascii=False)
        source = f"{request.extracted_text}\n{request.ocr_text}\n{preview_text}".lower()
        category_code = "UNKNOWN"
        category_label = "判定不能"
        confidence = 0.20
        reason = "分類に利用できる内容がありません。"
        for code, label, keywords in self._rules:
            if any(keyword.lower() in source for keyword in keywords):
                category_code = code
                category_label = label
                confidence = 0.95
                reason = "Mockキーワードルールに一致しました。"
                break
        else:
            if source.strip() and source.strip() not in ("[]",):
                category_code = "OTHER"
                category_label = "その他"
                confidence = 0.85
                reason = "既知の業務キーワードに一致しませんでした。"

        document_name = {
            "ORDER": "受注票",
            "INVENTORY": "在庫表",
            "SHIPPING": "出荷票",
            "OTHER": "その他帳票",
            "UNKNOWN": "不明",
        }[category_code]
        fields = []
        if request.extracted_text or request.ocr_text:
            fields.append(
                ExtractedField(
                    source_name="mock_content",
                    normalized_name="content",
                    value=(request.extracted_text or request.ocr_text)[:200],
                    data_type="string",
                    confidence=0.90,
                )
            )
        return AIAnalysisResult(
            document_category=DocumentCategory(
                code=category_code,
                label=category_label,
                confidence=confidence,
                reason=reason,
            ),
            document_type=DocumentType(
                name=document_name,
                confidence=0.90 if category_code != "UNKNOWN" else 0.20,
            ),
            provider_name=ConfidenceValue(value="Mock Provider", confidence=0.90),
            target_date=ConfidenceValue(value=None, confidence=0.50),
            fields=fields,
            summary=f"Mock分析結果: {category_label}",
            needs_review=category_code == "UNKNOWN",
        )
