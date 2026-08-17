import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from phase0_analyzer.config import get_settings
from phase0_analyzer.ui.home import (
    _analysis_duration,
    _category_label,
    _data_kind_label,
    _display_datetime,
    _field_name_for_user,
    _field_value_for_user,
    _next_action,
    _provider_for_user,
    _representative_table_for_display,
    _status_label,
    _table_preview_for_display,
)


def test_mixed_excel_preview_values_are_safe_for_display() -> None:
    preview = [
        {"sheet_name": "受注確認", "row_number": 1, "values": [1, "(金)", None]},
    ]

    display = _table_preview_for_display(preview)

    assert display == [
        {
            "sheet_name": "受注確認",
            "row_number": 1,
            "values": '[1, "(金)", null]',
        }
    ]
    assert preview[0]["values"] == [1, "(金)", None]


def test_representative_preview_limits_columns_and_preserves_order() -> None:
    preview = [
        {"sheet_name": "受注確認", "row_number": 1, "values": [None, "B", "C", "D"]},
        {"sheet_name": "受注確認", "row_number": 2, "values": [None, "2", None, "4"]},
    ]

    display, selected = _representative_table_for_display(preview, 2)

    assert selected == (1, 2)
    assert display[0] == {
        "シート": "受注確認",
        "行": 1,
        "列2": "B",
        "列3": "C",
    }


def test_business_labels_hide_internal_codes_and_guide_next_action() -> None:
    assert _status_label("READY") == "未分析"
    assert _status_label("ANALYZING") == "分析中"
    assert _status_label("COMPLETED") == "分析済み"
    assert _status_label("REVIEW_REQUIRED") == "要確認"
    assert _status_label("CONFIRMED") == "確認済み"
    assert _status_label("ERROR") == "エラー"
    assert _status_label("FAILED") == "エラー"
    assert _category_label("ORDER") == "受注・依頼"
    assert _provider_for_user("Mock Provider") == "未判定"
    assert _field_name_for_user("mock_content") == "読み取った内容"
    assert (
        _field_value_for_user("Mock OCRで抽出した帳票テキスト")
        == "検証用に読み取った帳票テキスト"
    )
    assert _display_datetime("2026-08-14T12:00:00+00:00").startswith("2026/08/14")
    assert _data_kind_label("INVENTORY") == "在庫データ"
    assert _analysis_duration(1234) == "1.2秒"
    assert _next_action("READY", False) == "「分析開始」を押す"
    assert _next_action("COMPLETED", True) == "結果を確認する"
    assert _next_action("REVIEW_REQUIRED", True) == "要確認箇所を確認する"


def test_file_is_registered_only_after_manual_refresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    (upload_dir / "order.csv").write_text("id,value\n1,100", encoding="utf-8")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("ORIGINAL_DIR", str(tmp_path / "original"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'startup.db'}")
    get_settings.cache_clear()
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "業務ファイル分析"
    assert any("登録だけでは分析されません" in item.value for item in app.markdown)
    assert (tmp_path / "startup.db").exists()
    assert app.button[0].label == "ファイル一覧を更新"

    with sqlite3.connect(tmp_path / "startup.db") as connection:
        file_count = connection.execute("SELECT COUNT(*) FROM files").fetchone()
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()
    assert file_count == (0,)
    assert analysis_count == (0,)

    app.button[0].click().run(timeout=30)

    with sqlite3.connect(tmp_path / "startup.db") as connection:
        file_count = connection.execute("SELECT COUNT(*) FROM files").fetchone()
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()
    assert file_count == (1,)
    assert analysis_count == (0,)
    assert app.dataframe

    analysis_button = next(button for button in app.button if button.label == "分析開始")
    analysis_button.click().run(timeout=30)

    with sqlite3.connect(tmp_path / "startup.db") as connection:
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()
        file_status = connection.execute("SELECT status FROM files").fetchone()
    assert analysis_count == (1,)
    assert file_status == ("COMPLETED",)
    assert any("分析が完了しました" in success.value for success in app.success)
    assert any(item.value == "分析結果" for item in app.subheader)
    assert any("要確認：0件" in success.value for success in app.success)
    assert any("分析時間:" in item.value for item in app.markdown)

    category_widget = next(
        selectbox for selectbox in app.selectbox if selectbox.label == "分類"
    )
    category_widget.set_value("SHIPPING")
    save_button = next(button for button in app.button if button.label == "修正内容を保存")
    save_button.click().run(timeout=30)
    with sqlite3.connect(tmp_path / "startup.db") as connection:
        correction_count = connection.execute(
            "SELECT COUNT(*) FROM correction_history"
        ).fetchone()
        original_category = connection.execute(
            "SELECT category_code FROM analysis_results"
        ).fetchone()
    assert correction_count == (1,)
    assert original_category == ("OTHER",)

    confirm_button = next(button for button in app.button if button.label == "結果を確定")
    confirm_button.click().run(timeout=30)
    with sqlite3.connect(tmp_path / "startup.db") as connection:
        confirmation = connection.execute(
            "SELECT confirmed_category_code FROM confirmed_results"
        ).fetchone()
        file_status = connection.execute("SELECT status FROM files").fetchone()
    assert confirmation == ("SHIPPING",)
    assert file_status == ("CONFIRMED",)

    reanalyze_button = next(button for button in app.button if button.label == "再分析")
    reanalyze_button.click().run(timeout=30)
    with sqlite3.connect(tmp_path / "startup.db") as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()
        confirmation_count = connection.execute(
            "SELECT COUNT(*) FROM confirmed_results"
        ).fetchone()
    assert run_count == (2,)
    assert confirmation_count == (1,)

    get_settings.cache_clear()


def test_validation_file_is_read_only_after_validation_action(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    upload_dir = tmp_path / "upload"
    validation_dir = tmp_path / "validation" / "actual"
    upload_dir.mkdir()
    validation_dir.mkdir(parents=True)
    (validation_dir / "inventory.csv").write_text(
        "商品,在庫\n商品A,10", encoding="utf-8"
    )
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("VALIDATION_DIR", str(validation_dir))
    monkeypatch.setenv("ORIGINAL_DIR", str(tmp_path / "original"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'validation.db'}")
    get_settings.cache_clear()

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path).run(timeout=30)

    with sqlite3.connect(tmp_path / "validation.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM files").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone() == (0,)

    validation_button = next(
        button for button in app.button if button.label == "検証ファイルを読み取る"
    )
    validation_button.click().run(timeout=30)

    with sqlite3.connect(tmp_path / "validation.db") as connection:
        file_row = connection.execute(
            "SELECT source_path, original_snapshot_path, status FROM files"
        ).fetchone()
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()
    assert Path(file_row[0]).parent == validation_dir
    assert Path(file_row[1]).is_file()
    assert file_row[2] == "READY"
    assert analysis_count == (0,)

    get_settings.cache_clear()
