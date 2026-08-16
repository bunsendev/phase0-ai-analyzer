"""Day 4 analysis orchestration called only by explicit user action."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from phase0_analyzer.ai_models import AIAnalysisResult, AnalysisRequest, AnalysisWarning
from phase0_analyzer.ai_input import prepare_ai_input
from phase0_analyzer.ai_provider import AIProvider
from phase0_analyzer.analysis_repository import AnalysisRepository
from phase0_analyzer.config import Settings
from phase0_analyzer.file_parsing import FileParsingService
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.ocr_provider import OCRProvider, OCRRequest
from phase0_analyzer.review import needs_review
from phase0_analyzer.snapshot import SnapshotError, SnapshotService


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    run_id: int
    run_number: int
    status: str
    result: AIAnalysisResult | None = None
    error_code: str | None = None
    error_message: str | None = None


class AnalysisService:
    def __init__(
        self,
        *,
        settings: Settings,
        files: FileRepository,
        parsing: FileParsingService,
        snapshots: SnapshotService,
        ocr: OCRProvider,
        ai: AIProvider,
        analyses: AnalysisRepository,
    ) -> None:
        self.settings = settings
        self.files = files
        self.parsing = parsing
        self.snapshots = snapshots
        self.ocr = ocr
        self.ai = ai
        self.analyses = analyses

    def analyze(self, file_id: int) -> AnalysisOutcome:
        """Run and append one analysis for the selected file ID."""
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        stored = self.files.get_by_id(file_id)
        if stored is None:
            return AnalysisOutcome(
                0, 0, "FAILED", error_code="FILE_ID_NOT_FOUND",
                error_message="指定されたファイルIDが見つかりません。",
            )
        self.files.update_status(file_id, "ANALYZING")
        try:
            snapshot_path = self.snapshots.ensure(file_id, self.files)
            parsed = self.parsing.parse(file_id)
            if not parsed.success:
                raise SnapshotError(parsed.error_message or "ファイル解析に失敗しました。")

            warnings = [
                AnalysisWarning(
                    code=warning.code,
                    severity="error" if warning.level == "error" else "warning",
                    message=warning.message,
                )
                for warning in parsed.warnings
            ]
            ocr_text = ""
            if parsed.requires_ocr:
                ocr_result = self.ocr.extract_text(
                    OCRRequest(
                        file_id=file_id,
                        file_path=Path(snapshot_path),
                        file_type=parsed.file_type,
                    )
                )
                ocr_text = ocr_result.text if ocr_result.success else ""
                warnings.extend(
                    AnalysisWarning(
                        code=warning.code,
                        severity="error" if warning.level == "error" else "warning",
                        message=warning.message,
                    )
                    for warning in ocr_result.warnings
                )
                if not ocr_result.success:
                    warnings.append(
                        AnalysisWarning(
                            code=ocr_result.error_code or "OCR_FAILED",
                            severity="error",
                            message=ocr_result.error_message or "OCR結果を取得できませんでした。",
                        )
                    )

            if parsed.requires_ocr and self.settings.ocr_review_required:
                warnings.append(
                    AnalysisWarning(
                        code="OCR_REVIEW_REQUIRED",
                        severity="warning",
                        message="画像・手書き帳票のため、OCR結果を確認してください。",
                    )
                )

            ai_input = prepare_ai_input(
                parsed,
                ocr_text,
                max_columns=self.settings.ai_max_columns,
                max_characters=self.settings.ai_max_input_chars,
            )
            warnings.extend(ai_input.warnings)

            request = AnalysisRequest(
                file_id=file_id,
                file_name=parsed.file_name,
                file_type=parsed.file_type,
                extracted_text=ai_input.extracted_text,
                table_preview=ai_input.table_preview,
                parser_metadata=ai_input.parser_metadata,
                parse_warnings=warnings,
                ocr_text=ai_input.ocr_text,
                requires_ocr=parsed.requires_ocr,
                previous_examples=[],
            )
            ai_result = self.ai.analyze(request)
            warnings.extend(ai_result.warnings)
            review_required = needs_review(
                ai_result,
                warnings,
                parsed.requires_ocr,
                ocr_text,
                self.settings.category_confidence_threshold,
                self.settings.document_type_confidence_threshold,
            )
            status = "REVIEW_REQUIRED" if review_required else "COMPLETED"
            completed_at = datetime.now(UTC)
            saved = self.analyses.save_success(
                file_id=file_id,
                status=status,
                provider=self.ai.provider_name,
                model_name=self.ai.model_name,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=int((perf_counter() - started_clock) * 1000),
                extracted_text=parsed.extracted_text + (f"\n{ocr_text}" if ocr_text else ""),
                raw_ai_response=ai_result.model_dump_json(),
                result=ai_result,
                warnings=warnings,
            )
            self.files.update_status(file_id, status)
            return AnalysisOutcome(saved.id, saved.run_number, status, ai_result)
        except Exception as error:
            completed_at = datetime.now(UTC)
            error_code = error.code if hasattr(error, "code") else "ANALYSIS_FAILED"
            message = str(error) or "分析処理に失敗しました。"
            saved = self.analyses.save_failure(
                file_id=file_id,
                provider=self.ai.provider_name,
                model_name=self.ai.model_name,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=int((perf_counter() - started_clock) * 1000),
                error_code=error_code,
                error_message=message,
            )
            self.files.update_status(file_id, "FAILED")
            return AnalysisOutcome(
                saved.id, saved.run_number, "FAILED",
                error_code=error_code, error_message=message,
            )
