# Phase0 AI Analyzer

受注・在庫・出荷配送などの業務ファイルを、利用者の明示的な操作で分析する1週間のプロトタイプです。Day 7では、原本snapshot、Mock OCR/AI、分析履歴、詳細確認、追記型修正、確定、再分析、OCR要確認、AI入力上限までを実装しています。実OCR・OpenAI接続はまだ実装していません。

## 前提

- Python 3.11以上
- PowerShell（以下はWindowsでの例）

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

`.env`の初期値は`AI_PROVIDER=mock`です。APIキーは不要です。`.env`はGit管理対象外です。

OCR対象の要確認は`OCR_REVIEW_REQUIRED`、AI入力は`AI_MAX_COLUMNS`と`AI_MAX_INPUT_CHARS`で設定できます。既定値は要確認有効、100列、100,000文字です。

## 起動

```powershell
streamlit run app.py
```

ブラウザで表示されたURLを開きます。初回起動時に`data/database/phase0.db`と必要なSQLiteテーブルが作成されます。

`data/upload/`へファイルを置いただけでは、登録も分析も始まりません。画面の「ファイル一覧を更新」を押すと、直下のファイル情報だけをSQLiteへ登録して一覧表示します。この操作はファイル内容解析や分析を実行しません。

Day 6の実データ検証では、Git管理外の`data/validation/actual/`を使用できます。配置だけでは読み取らず、画面の「検証ファイルを読み取る」を押した場合だけ登録します。登録後は通常ファイルと同じsnapshot、Parser、分析、修正、確定フローを使用します。

対応形式は`xlsx`、`csv`、`pdf`、`png`、`jpg`、`jpeg`です。それ以外のファイルも一覧へ登録されますが、ステータスは`UNSUPPORTED`になります。

CSV構造のTXTを検証する場合は、元ファイルを変更せずCP932のまま`.csv`コピーを作成してください。TXT Parserはフェーズ0では追加していません。

一覧で「未分析」のファイルを選び「分析開始」を押した場合だけ、snapshotを使った解析、必要時のMock OCR、Mock AI、履歴保存を実行します。配置や「ファイル一覧を更新」では分析しません。

## テスト

```powershell
pytest
```

設定読込、SQLite初期化、snapshot、各形式の解析、Mock OCR・AI、履歴追記、要確認判定、Streamlitの明示的な分析開始フローを確認します。

## ディレクトリ構成

```text
app.py                         Streamlitエントリーポイント
src/phase0_analyzer/config.py  環境変数・.env読込
src/phase0_analyzer/database.py SQLite初期化
src/phase0_analyzer/parsers/   Excel、CSV、PDF、画像パーサー
src/phase0_analyzer/file_parsing.py file_id基準の解析サービス
src/phase0_analyzer/ocr_provider.py 将来のOCR Provider境界
src/phase0_analyzer/ai_provider.py Mock AI Provider
src/phase0_analyzer/analysis_service.py 分析オーケストレーター
src/phase0_analyzer/analysis_repository.py 分析履歴の追記保存
src/phase0_analyzer/snapshot.py 原本snapshot保存
src/phase0_analyzer/ui/        画面表示
tests/                         最低限の自動テスト
data/upload/                   利用者向け共通配置先
data/validation/actual/        Git管理外の実データ検証用配置先
data/database/                 ローカルSQLite保存先
docs/                          要件・計画・判断記録
```

## 最初に読む文書

1. `AGENTS.md`
2. `docs/requirements.md`
3. `docs/implementation-plan.md`
4. `docs/day1-guide.md`

## プロトタイプの原則

- ファイル配置だけでは分析しない
- 利用者が分析開始ボタンを押した場合のみ処理する
- `AI_PROVIDER=mock`で一連動作できるようにする
- 過去の分析結果と修正履歴を上書きしない
- 本番認証、外部連携、自動取込などを追加しない
