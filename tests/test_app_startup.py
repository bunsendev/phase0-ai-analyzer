import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from phase0_analyzer.config import get_settings


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
    assert app.title[0].value == "Phase0 AI Analyzer"
    assert any("配置しただけでは登録も分析も開始されません" in item.value for item in app.info)
    assert (tmp_path / "startup.db").exists()
    assert app.button[0].label == "一覧更新"

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
    assert any("COMPLETED" in success.value for success in app.success)

    category_widget = next(
        selectbox for selectbox in app.selectbox if selectbox.label == "大分類（現在値）"
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

    reanalyze_button = next(button for button in app.button if button.label == "分析開始")
    reanalyze_button.click().run(timeout=30)
    with sqlite3.connect(tmp_path / "startup.db") as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()
        confirmation_count = connection.execute(
            "SELECT COUNT(*) FROM confirmed_results"
        ).fetchone()
    assert run_count == (2,)
    assert confirmation_count == (1,)

    get_settings.cache_clear()
