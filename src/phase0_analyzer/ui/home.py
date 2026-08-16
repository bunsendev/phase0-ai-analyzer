"""Task 1 startup screen."""

import json
from datetime import datetime

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
from phase0_analyzer.parsers.models import ParseResult
from phase0_analyzer.result_service import ResultDetail, ResultService
from phase0_analyzer.snapshot import SnapshotError, SnapshotService


STATUS_LABELS = {
    "READY": "未分析",
    "ANALYZING": "分析中",
    "COMPLETED": "分析済み",
    "REVIEW_REQUIRED": "要確認",
    "CONFIRMED": "確認済み",
    "ERROR": "エラー",
    "FAILED": "エラー",
    "UNSUPPORTED": "対応外",
    "EXCLUDED": "対象外",
}

CATEGORY_LABELS = {
    "ORDER": "受注・依頼",
    "INVENTORY": "在庫",
    "SHIPPING": "出荷・配送",
    "OTHER": "その他",
    "UNKNOWN": "判定不能",
}


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "不明")


def _category_label(category_code: str | None) -> str:
    if not category_code:
        return "未分析"
    return CATEGORY_LABELS.get(category_code, "判定不能")


def _data_kind_label(category_code: str | None) -> str:
    label = _category_label(category_code)
    return label if label in {"その他", "判定不能", "未分析"} else f"{label}データ"


def _display_datetime(value: str | None) -> str:
    if not value:
        return "処理中"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y/%m/%d %H:%M")
    except ValueError:
        return value


def _analysis_duration(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "計測なし"
    return f"{duration_ms / 1000:.1f}秒"


def _provider_for_user(value: str | None) -> str:
    return "未判定" if not value or value == "Mock Provider" else value


def _field_value_for_user(value: str | None) -> str:
    if value == "Mock OCRで抽出した帳票テキスト":
        return "検証用に読み取った帳票テキスト"
    return value or ""


def _field_name_for_user(value: str | None) -> str:
    if value == "mock_content":
        return "読み取った内容"
    if value == "content":
        return "内容"
    return value or ""


def _next_action(status: str, has_result: bool) -> str:
    if status == "READY":
        return "「分析開始」を押す"
    if status == "ANALYZING":
        return "分析完了を待つ"
    if status == "REVIEW_REQUIRED":
        return "要確認箇所を確認する"
    if status == "COMPLETED":
        return "結果を確認する"
    if status == "CONFIRMED":
        return "操作完了"
    if status in {"ERROR", "FAILED"}:
        return "「再分析」を押す"
    if status == "UNSUPPORTED":
        return "対応形式へ変換"
    return "結果を見る" if has_result else "状態を確認"


def _review_messages(detail: ResultDetail) -> list[str]:
    messages: list[str] = []
    if detail.result["category_code"] == "UNKNOWN":
        messages.append("分類を判定できませんでした。元データと分類を確認してください。")
    elif detail.result["category_confidence"] < 0.80:
        messages.append("分類の確かさが低いため、分類が正しいか確認してください。")
    if detail.result["document_type_confidence"] < 0.70:
        messages.append("帳票種類の確かさが低いため、帳票種類を確認してください。")

    seen_warning_codes: set[str] = set()
    for warning in detail.warnings:
        if warning["severity"] not in {"warning", "error"}:
            continue
        if warning["code"] in seen_warning_codes:
            continue
        seen_warning_codes.add(warning["code"])
        messages.append(warning["message"])

    for field in detail.fields:
        if field["needs_review"]:
            messages.append(
                f'「{_field_name_for_user(field["source_name"])}」の内容を確認してください。'
            )
    if detail.review_count and not messages:
        messages.append("分析結果を元データと比較してください。")
    return messages


def _table_preview_for_display(
    table_preview: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Make nested spreadsheet rows safe for Streamlit's Arrow conversion."""
    display_rows: list[dict[str, object]] = []
    for row in table_preview:
        display_row = dict(row)
        values = display_row.get("values")
        if isinstance(values, list):
            display_row["values"] = json.dumps(values, ensure_ascii=False, default=str)
        display_rows.append(display_row)
    return display_rows


def _representative_table_for_display(
    table_preview: list[dict[str, object]], max_columns: int
) -> tuple[list[dict[str, str | int]], tuple[int, ...]]:
    """Flatten the first non-empty columns into an Arrow-safe table."""
    value_rows = [
        row.get("values") for row in table_preview if isinstance(row.get("values"), list)
    ]
    total_columns = max((len(row) for row in value_rows), default=0)
    selected = tuple(
        column
        for column in range(total_columns)
        if any(column < len(row) and row[column] not in (None, "") for row in value_rows)
    )[:max_columns]
    display: list[dict[str, str | int]] = []
    for row in table_preview:
        values = row.get("values")
        if not isinstance(values, list):
            continue
        display_row: dict[str, str | int] = {
            "シート": str(row.get("sheet_name", "")),
            "行": int(row.get("row_number", 0)),
        }
        for column in selected:
            value = values[column] if column < len(values) else None
            display_row[f"列{column + 1}"] = "" if value is None else str(value)
        display.append(display_row)
    return display, selected


def _parsed_total_columns(parsed: ParseResult) -> int:
    if parsed.file_type == "xlsx":
        return max(
            (int(sheet.get("column_count", 0)) for sheet in parsed.metadata.get("sheets", [])),
            default=0,
        )
    return int(parsed.metadata.get("column_count", 0))


def render_home(settings: Settings) -> None:
    """Render the manual file refresh and registered-file list."""
    st.set_page_config(page_title="業務ファイル分析", page_icon="📄")
    st.title("業務ファイル分析")
    st.caption("ファイルを登録し、必要なものだけ分析して、結果を確認します。")

    step_columns = st.columns(3)
    step_columns[0].markdown("**① ファイル登録**  \n一覧を最新にします")
    step_columns[1].markdown("**② 分析開始**  \n対象を1件選びます")
    step_columns[2].markdown("**③ 結果確認**  \n確認・修正して確定します")

    repository = FileRepository(settings.database_path)
    snapshot_service = SnapshotService(settings.resolve_path(settings.original_dir))

    st.divider()
    st.header("① ファイル登録")
    st.write("共有フォルダに置いたファイルを一覧へ登録します。登録だけでは分析されません。")
    if st.button("ファイル一覧を更新", type="primary"):
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

    with st.expander("検証用ファイルを使用する"):
        st.caption(
            "検証担当者向けの操作です。ファイルを置いただけでは登録・分析されません。"
        )
        if st.button("検証ファイルを読み取る"):
            try:
                summary = register_discovered_files(
                    settings.resolve_path(settings.validation_dir),
                    repository,
                    snapshot_service,
                )
                st.success(
                    f"検証ファイル{summary.detected_count}件を検出し、"
                    f"{summary.registered_count}件を登録しました。"
                    f"（登録済み: {summary.duplicate_count}件）"
                )
            except (FileDiscoveryError, SnapshotError) as error:
                st.error(str(error))

    st.divider()
    st.header("② 分析開始")
    st.write("一覧で状態を確認し、分析するファイルを1件選んでください。")
    files = repository.list_all()
    if not files:
        st.info("登録済みのファイルはありません。共有フォルダへファイルを置き、「ファイル一覧を更新」を押してください。")
        return

    result_service = ResultService(settings.database_path, repository)
    latest_results = result_service.latest_by_file()
    st.dataframe(
        [
            {
                "ファイル名": file.file_name,
                "ファイル形式": file.extension.upper().lstrip("."),
                "状態": _status_label(file.status),
                "最新分析結果": (
                    f"{_category_label(latest_results[file.id].category_code)} / "
                    f"{latest_results[file.id].document_type or '帳票種類不明'}"
                    if file.id in latest_results else "未分析"
                ),
                "要確認": (
                    f"要確認 {latest_results[file.id].review_count}件"
                    if file.id in latest_results
                    and latest_results[file.id].review_count > 0
                    else "なし"
                ),
                "次に行う操作": _next_action(
                    file.status, file.id in latest_results
                ),
            }
            for file in files
        ],
        width="stretch",
        hide_index=True,
    )

    ready_files = [
        file for file in files
        if file.status in {
            "READY", "ANALYZING", "COMPLETED", "REVIEW_REQUIRED",
            "FAILED", "ERROR", "CONFIRMED",
        }
    ]
    if ready_files:
        labels = {
            file.id: f"{file.file_name}（{_status_label(file.status)}）"
            for file in ready_files
        }
        selected_id = st.selectbox(
            "分析するファイル", options=list(labels), format_func=lambda file_id: labels[file_id]
        )
        selected_file = next(file for file in ready_files if file.id == selected_id)
        selected_has_runs = bool(result_service.list_runs(selected_id))
        analysis_requested = False
        if selected_file.status == "READY":
            st.info("このファイルはまだ分析されていません。")
            analysis_requested = st.button("分析開始", type="primary")
        elif selected_file.status == "ANALYZING":
            st.info("このファイルを分析しています。完了までお待ちください。")
        elif selected_file.status == "REVIEW_REQUIRED":
            st.warning("分析結果に確認が必要な項目があります。下の「③ 結果確認」を確認してください。")
        elif selected_file.status == "COMPLETED":
            st.info("分析が完了しました。下の「③ 結果確認」で内容を確認してください。")
        elif selected_file.status == "CONFIRMED":
            st.success("担当者による確認が完了しています。")
        elif selected_file.status in {"FAILED", "ERROR"}:
            st.error("前回の分析でエラーが発生しました。内容を確認して再分析してください。")
            analysis_requested = st.button("再分析", type="primary")

        if selected_has_runs and selected_file.status not in {
            "ANALYZING", "FAILED", "ERROR"
        }:
            with st.expander("必要な場合だけ再分析"):
                st.caption("再分析すると新しい分析履歴が追加され、過去の結果は残ります。")
                analysis_requested = st.button("再分析", key=f"reanalyze-{selected_id}")

        if analysis_requested:
            if settings.ai_provider != "mock":
                st.error("現在の設定では分析を開始できません。管理者へ連絡してください。")
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
                elif outcome.status == "REVIEW_REQUIRED":
                    st.warning("分析が完了しました。確認が必要な箇所があります。下の「③ 結果確認」を開いてください。")
                else:
                    st.success("分析が完了しました。下の「③ 結果確認」で内容を確認してください。")

    selected_runs = (
        [
            run for run in result_service.list_runs(selected_id)
            if run.status != "FAILED"
        ]
        if ready_files else []
    )
    if ready_files:
        st.divider()
        st.header("③ 結果確認")
        if not selected_runs:
            if selected_file.status == "ANALYZING":
                st.info("分析が完了すると、ここに結果が表示されます。")
            elif selected_file.status in {"FAILED", "ERROR"}:
                st.info("表示できる分析結果がありません。②の「再分析」を押してください。")
            else:
                st.info("このファイルはまだ分析されていません。②の「分析開始」を押してください。")
            return
        st.write(
            f'「{selected_file.file_name}」のAI判断と要確認箇所を確認し、'
            "必要なら修正して結果を確定してください。"
        )
        run_labels = {
            run.id: (
                f"最新の分析結果（{_display_datetime(run.completed_at)}）"
                if index == 0 else
                f"過去の分析結果 {index}（{_display_datetime(run.completed_at)}）"
            )
            for index, run in enumerate(selected_runs)
        }
        selected_run_id = st.selectbox(
            "表示する分析履歴",
            options=list(run_labels),
            format_func=lambda run_id: run_labels[run_id],
        )
        try:
            detail = result_service.get_detail(selected_run_id)
        except ValueError as error:
            st.warning(str(error))
            return

        st.subheader("分析結果")
        st.markdown(f'## {_data_kind_label(detail.result["category_code"])}')

        review_reasons = _review_messages(detail)
        if detail.review_count:
            st.warning(
                f"要確認：{detail.review_count}件\n\n"
                + "\n\n".join(review_reasons)
            )
        else:
            st.success("要確認：0件。内容を確認し、問題がなければ確定してください。")

        if detail.confirmation:
            st.info("担当者による確認が完了しています。必要な場合は修正して、もう一度確定できます。")

        st.subheader("主な内容")
        result_columns = st.columns(3)
        result_columns[0].metric("帳票種類", detail.result["document_type"] or "不明")
        result_columns[1].metric("対象日", detail.result["target_date"] or "不明")
        result_columns[2].metric("提供元", _provider_for_user(detail.result["provider_name"]))
        if detail.fields:
            st.dataframe(
                [
                    {
                        "項目": _field_name_for_user(
                            detail.current[("field_normalized_name", field["id"])]
                            or field["source_name"]
                        ),
                        "内容": _field_value_for_user(
                            detail.current[("field_value", field["id"])]
                        ),
                        "確認": "要確認" if field["needs_review"] else "",
                    }
                    for field in detail.fields
                ],
                width="stretch",
                hide_index=True,
            )

        st.subheader("元データ")
        st.caption(f'{detail.file["file_name"]}（{detail.file["extension"].upper().lstrip(".")}）')
        parsed = FileParsingService(repository, ParserResolver(settings)).parse(
            detail.file["id"]
        )
        if parsed.file_type in {"csv", "xlsx"} and parsed.table_preview:
            representative, selected_columns = _representative_table_for_display(
                parsed.table_preview[:50], settings.ai_max_columns
            )
            total_columns = _parsed_total_columns(parsed)
            st.caption(
                f"全{total_columns}列中、現在{len(selected_columns)}列を表示しています。"
            )
            st.dataframe(representative, width="stretch", hide_index=True)
            with st.expander("元データの全列を表示"):
                st.dataframe(
                    _table_preview_for_display(parsed.table_preview[:50]),
                    width="stretch",
                    hide_index=True,
                )
        elif parsed.file_type == "pdf":
            st.text_area("文書から読み取った内容", parsed.extracted_text, disabled=True)
        elif parsed.file_type in {"png", "jpg", "jpeg"}:
            st.image(detail.file["original_snapshot_path"], caption=detail.file["file_name"])
        elif not parsed.success:
            st.warning(parsed.error_message or "元データを表示できませんでした。")

        st.subheader("修正・確認")
        st.write("AIの判断に誤りがある場合だけ修正してください。変更した内容は履歴に残ります。")
        categories = ["ORDER", "INVENTORY", "SHIPPING", "OTHER", "UNKNOWN"]
        current_category = detail.current[("category", None)] or "UNKNOWN"
        category = st.selectbox(
            "分類",
            categories,
            index=categories.index(current_category),
            format_func=_category_label,
            key=f"category-{selected_run_id}",
        )
        document_type = st.text_input(
            "帳票種類",
            value=detail.current[("document_type", None)] or "",
            key=f"document-{selected_run_id}",
        )
        current_provider = detail.current[("provider_name", None)]
        provider_name = st.text_input(
            "提供元",
            value="" if current_provider == "Mock Provider" else current_provider or "",
            placeholder="分かる場合に入力",
            key=f"provider-user-{selected_run_id}",
        )
        target_date = st.text_input(
            "対象日", value=detail.current[("target_date", None)] or "",
            key=f"date-{selected_run_id}",
        )

        changes = {
            ("category", None): category,
            ("document_type", None): document_type or None,
            ("provider_name", None): (
                current_provider
                if current_provider == "Mock Provider" and not provider_name
                else provider_name or None
            ),
            ("target_date", None): target_date or None,
        }
        if detail.fields:
            st.markdown("**読み取った項目**")
        for field in detail.fields:
            source_name = _field_name_for_user(field["source_name"])
            is_mock_field = field["source_name"] == "mock_content"
            current_normalized = detail.current[
                ("field_normalized_name", field["id"])
            ]
            displayed_normalized = _field_name_for_user(current_normalized)
            current_field_value = detail.current[("field_value", field["id"])]
            displayed_field_value = _field_value_for_user(current_field_value)
            normalized = st.text_input(
                "項目名" if is_mock_field else f'{source_name}の項目名',
                value=displayed_normalized,
                key=f'field-name-user-{selected_run_id}-{field["id"]}',
            )
            value = st.text_input(
                "読み取った内容" if is_mock_field else f'{source_name}の内容',
                value=displayed_field_value,
                key=f'field-value-user-{selected_run_id}-{field["id"]}',
            )
            changes[("field_normalized_name", field["id"])] = (
                current_normalized
                if normalized == displayed_normalized else normalized or None
            )
            changes[("field_value", field["id"])] = (
                current_field_value if value == displayed_field_value else value or None
            )

        if st.button("修正内容を保存"):
            count = result_service.save_corrections(
                selected_run_id, changes, settings.default_user
            )
            st.success(f"{count}件の修正履歴を保存しました。")
        if st.button("結果を確定"):
            result_service.confirm(selected_run_id, settings.default_user)
            st.success("結果を確定しました。")

        with st.expander("詳細情報（開発・調査用）"):
            st.write(f'分析開始日時: {_display_datetime(detail.run["started_at"])}')
            st.write(f'分析完了日時: {_display_datetime(detail.run["completed_at"])}')
            st.write(f'分析時間: {_analysis_duration(detail.run["duration_ms"])}')
            st.write(
                f'分析履歴番号: {detail.run["run_number"]} / '
                f'処理方式: {detail.run["provider"]} / '
                f'モデル: {detail.run["model_name"]} / '
                f'状態: {_status_label(detail.run["status"])}'
            )
            st.write(
                f'分類confidence: {detail.result["category_confidence"]:.2f} / '
                f'帳票種類confidence: {detail.result["document_type_confidence"]:.2f}'
            )
            st.caption(f'判定理由: {detail.result["category_reason"]}')
            if detail.confirmation:
                st.write(
                    f'確定日時: {detail.confirmation["confirmed_at"]} / '
                    f'確定者: {detail.confirmation["confirmed_by"]}'
                )
            if detail.warnings:
                st.markdown("**警告情報**")
                st.dataframe(detail.warnings, width="stretch", hide_index=True)
            st.markdown("**Parser metadata**")
            st.json(parsed.metadata)
            st.markdown("**raw AI response**")
            st.json(detail.result)
