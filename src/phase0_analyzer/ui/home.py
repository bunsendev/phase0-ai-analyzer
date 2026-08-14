"""Task 1 startup screen."""

import streamlit as st

from phase0_analyzer.config import Settings
from phase0_analyzer.ai_provider import MockAIProvider
from phase0_analyzer.analysis_repository import AnalysisRepository
from phase0_analyzer.analysis_service import AnalysisService
from phase0_analyzer.file_parsing import FileParsingService
from phase0_analyzer.file_discovery import FileDiscoveryError
from phase0_analyzer.file_registration import register_discovered_files
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.ocr_provider import MockOCRProvider
from phase0_analyzer.parsers.resolver import ParserResolver
from phase0_analyzer.result_service import ResultService
from phase0_analyzer.snapshot import SnapshotError, SnapshotService


def render_home(settings: Settings) -> None:
    """Render the manual file refresh and registered-file list."""
    st.set_page_config(page_title="Phase0 AI Analyzer", page_icon="📄")
    st.title("Phase0 AI Analyzer")
    st.write("共有アップロードフォルダに配置されたファイルを確認します。")
    st.info("ファイルを配置しただけでは登録も分析も開始されません。")

    st.subheader("現在の設定")
    st.text(f"実行環境: {settings.app_env}")
    st.text(f"AIプロバイダー: {settings.ai_provider}")
    st.text(f"アップロード先: {settings.resolve_path(settings.upload_dir)}")

    repository = FileRepository(settings.database_path)
    snapshot_service = SnapshotService(settings.resolve_path(settings.original_dir))
    if st.button("一覧更新", type="primary"):
        try:
            summary = register_discovered_files(
                settings.resolve_path(settings.upload_dir), repository, snapshot_service
            )
            st.success(
                f"{summary.detected_count}件を検出し、"
                f"{summary.registered_count}件を新規登録しました。"
                f"（登録済み: {summary.duplicate_count}件）"
            )
        except (FileDiscoveryError, SnapshotError) as error:
            st.error(str(error))

    st.subheader("ファイル一覧")
    files = repository.list_all()
    if not files:
        st.caption("登録済みのファイルはありません。")
        return

    st.dataframe(
        [
            {
                "ファイル名": file.file_name,
                "拡張子": file.extension,
                "ファイルサイズ（bytes）": file.size_bytes,
                "更新日時": file.modified_at,
                "登録日時": file.registered_at,
                "ステータス": file.status,
            }
            for file in files
        ],
        width="stretch",
        hide_index=True,
    )

    ready_files = [
        file for file in files
        if file.status in {"READY", "COMPLETED", "REVIEW_REQUIRED", "FAILED", "CONFIRMED"}
    ]
    if ready_files:
        labels = {file.id: f"{file.id}: {file.file_name}" for file in ready_files}
        selected_id = st.selectbox(
            "分析対象", options=list(labels), format_func=lambda file_id: labels[file_id]
        )
        if st.button("分析開始"):
            if settings.ai_provider != "mock":
                st.error("Day 4ではAI_PROVIDER=mockだけを利用できます。")
            else:
                service = AnalysisService(
                    settings=settings,
                    files=repository,
                    parsing=FileParsingService(repository, ParserResolver(settings)),
                    snapshots=snapshot_service,
                    ocr=MockOCRProvider(),
                    ai=MockAIProvider(),
                    analyses=AnalysisRepository(settings.database_path),
                )
                outcome = service.analyze(selected_id)
                if outcome.status == "FAILED":
                    st.error(outcome.error_message or "分析に失敗しました。")
                else:
                    st.success(
                        f"分析実行 #{outcome.run_number}: {outcome.status}"
                    )

    result_service = ResultService(settings.database_path, repository)
    files_with_runs = [file for file in files if result_service.list_runs(file.id)]
    if files_with_runs:
        st.divider()
        st.header("分析結果詳細")
        detail_labels = {file.id: f"{file.id}: {file.file_name}" for file in files_with_runs}
        detail_file_id = st.selectbox(
            "詳細対象ファイル",
            options=list(detail_labels),
            format_func=lambda file_id: detail_labels[file_id],
        )
        runs = result_service.list_runs(detail_file_id)
        run_labels = {
            run.id: f"Run {run.run_number} - {run.completed_at or run.status}" for run in runs
        }
        selected_run_id = st.selectbox(
            "分析run", options=list(run_labels), format_func=lambda run_id: run_labels[run_id]
        )
        try:
            detail = result_service.get_detail(selected_run_id)
        except ValueError as error:
            st.warning(str(error))
            return

        review_reasons = []
        if detail.result["needs_review"]:
            review_reasons.append("分析結果が要確認です。")
        if detail.result["category_code"] == "UNKNOWN":
            review_reasons.append("大分類がUNKNOWNです。")
        review_reasons.extend(
            f'{warning["severity"]}: {warning["message"]}' for warning in detail.warnings
        )
        review_reasons.extend(
            f'要確認項目: {field["source_name"]}'
            for field in detail.fields if field["needs_review"]
        )
        if review_reasons:
            st.warning("\n\n".join(review_reasons))
        else:
            st.success("要確認項目はありません。修正不要ならそのまま確定できます。")

        st.write(
            f'Run {detail.run["run_number"]} / {detail.run["provider"]} / '
            f'{detail.run["model_name"]} / {detail.run["completed_at"]}'
        )
        if detail.confirmation:
            st.info(
                f'確定済み: {detail.confirmation["confirmed_at"]} / '
                f'{detail.confirmation["confirmed_by"]}'
            )

        categories = ["ORDER", "INVENTORY", "SHIPPING", "OTHER", "UNKNOWN"]
        current_category = detail.current[("category", None)] or "UNKNOWN"
        category = st.selectbox(
            "大分類（現在値）", categories,
            index=categories.index(current_category), key=f"category-{selected_run_id}"
        )
        document_type = st.text_input(
            "帳票種類（現在値）",
            value=detail.current[("document_type", None)] or "",
            key=f"document-{selected_run_id}",
        )
        provider_name = st.text_input(
            "提供元（現在値）", value=detail.current[("provider_name", None)] or "",
            key=f"provider-{selected_run_id}",
        )
        target_date = st.text_input(
            "対象日（現在値）", value=detail.current[("target_date", None)] or "",
            key=f"date-{selected_run_id}",
        )
        st.caption(
            f'AI元結果: {detail.result["category_code"]} '
            f'({detail.result["category_confidence"]:.2f}) / '
            f'{detail.result["category_reason"]}'
        )
        st.write(f'AI要約: {detail.result["summary"]}')

        changes = {
            ("category", None): category,
            ("document_type", None): document_type or None,
            ("provider_name", None): provider_name or None,
            ("target_date", None): target_date or None,
        }
        if detail.fields:
            st.subheader("抽出項目")
        for field in detail.fields:
            normalized = st.text_input(
                f'{field["source_name"]} 共通項目名',
                value=detail.current[("field_normalized_name", field["id"])] or "",
                key=f'field-name-{selected_run_id}-{field["id"]}',
            )
            value = st.text_input(
                f'{field["source_name"]} 値',
                value=detail.current[("field_value", field["id"])] or "",
                key=f'field-value-{selected_run_id}-{field["id"]}',
            )
            changes[("field_normalized_name", field["id"])] = normalized or None
            changes[("field_value", field["id"])] = value or None

        if st.button("修正内容を保存"):
            count = result_service.save_corrections(
                selected_run_id, changes, settings.default_user
            )
            st.success(f"{count}件の修正履歴を保存しました。")
        if st.button("結果を確定"):
            result_service.confirm(selected_run_id, settings.default_user)
            st.success("結果を確定しました。")

        with st.expander("警告・元データを確認"):
            if detail.warnings:
                st.dataframe(detail.warnings, width="stretch", hide_index=True)
            parsed = FileParsingService(repository, ParserResolver(settings)).parse(
                detail.file["id"]
            )
            if parsed.file_type in {"csv", "xlsx"} and parsed.table_preview:
                st.dataframe(parsed.table_preview[:50], width="stretch", hide_index=True)
            elif parsed.file_type == "pdf":
                st.text_area("PDF抽出テキスト", parsed.extracted_text, disabled=True)
            elif parsed.file_type in {"png", "jpg", "jpeg"}:
                st.image(detail.file["original_snapshot_path"], caption=detail.file["file_name"])
