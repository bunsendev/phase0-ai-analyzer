# Day 3完了報告

- 更新日: 2026-08-14
- 基準文書: `AGENTS.md`、`docs/requirements.md`、`docs/implementation-plan.md`
- 現在地点: Day 3完了、Day 4着手可能

## 1. 変更したファイル

### 新規モジュール

- `src/phase0_analyzer/file_parsing.py`
- `src/phase0_analyzer/ocr_provider.py`
- `src/phase0_analyzer/parsers/__init__.py`
- `src/phase0_analyzer/parsers/base.py`
- `src/phase0_analyzer/parsers/models.py`
- `src/phase0_analyzer/parsers/excel.py`
- `src/phase0_analyzer/parsers/csv_parser.py`
- `src/phase0_analyzer/parsers/pdf.py`
- `src/phase0_analyzer/parsers/image.py`
- `src/phase0_analyzer/parsers/resolver.py`

### 新規テスト

- `tests/test_excel_parser.py`
- `tests/test_csv_parser.py`
- `tests/test_pdf_parser.py`
- `tests/test_image_parser.py`
- `tests/test_file_parsing.py`

### 更新ファイル

- `pyproject.toml`
- `src/phase0_analyzer/config.py`
- `src/phase0_analyzer/file_repository.py`
- `README.md`
- `docs/decisions.md`
- `docs/known-issues.md`
- `docs/day3-result.md`

## 2. 新しく追加したクラス・モジュール

- `BaseParser`
- `ParseResult`
- `ParseWarning`
- `ParseError`
- `ExcelParser`
- `CsvParser`
- `PdfParser`
- `ImageParser`
- `UnsupportedParser`
- `ParserResolver`
- `FileParsingService`
- `OCRProvider`
- `OCRRequest`
- `OCRResult`

## 3. 各パーサーの動作

### Excel

- 複数シートを認識
- シート名、行数、列数を取得
- ヘッダー候補を取得
- 各シートの先頭最大100行を取得
- 数式、結合セル、空白行、空白列を判定
- 全シート合計で最大30行の`table_preview`を作成
- 元のxlsxファイルは変更しない

### CSV

- UTF-8、UTF-8 BOM、CP932、Shift_JISの順で読取
- 使用した文字コードを記録
- 区切り文字、行数、列数、ヘッダー候補を取得
- 先頭最大100行を取得
- 列数不一致を警告
- 区切り文字を推定できない場合はカンマへフォールバックして警告
- 読取不能時は例外を外へ出さず、失敗`ParseResult`を返す

### PDF

- `PDF_MAX_PAGES`までテキストを抽出
- ページ数、解析ページ数、抽出文字数を取得
- `PDF_TEXT_THRESHOLD`以上をテキストPDFと判定
- 閾値未満を画像PDFとして`requires_ocr=true`に設定
- ページ上限超過はエラーにせず警告
- OCRそのものは実行しない

### 画像

- PNG、JPG、JPEGに対応
- 幅、高さ、画像形式、ファイルサイズを取得
- 正常画像は原則`requires_ocr=true`
- 幅または高さが500px未満の場合に警告
- 破損画像では警告付きの失敗`ParseResult`を返す
- OCRそのものは実行しない

### 対応外形式

- `UnsupportedParser`を選択
- `UNSUPPORTED_FILE_TYPE`の明示的な失敗結果を返す

## 4. file_id基準の解析

`FileParsingService`は最新ファイルを検索せず、指定された`files.id`のレコードを取得します。

解析前に登録済みSHA-256と現在の実ファイルを照合します。内容が変更されている場合は、別バージョンを誤って解析せず`FILE_VERSION_MISMATCH`を返します。

Day 3の解析では、`analysis_runs`やAI結果を作成しません。

## 5. OCR Provider境界

将来のOCR実装向けに以下を追加しました。

- `OCRProvider` Protocol
- `OCRRequest`
- `OCRResult`

以下は未実装です。

- 実OCRサービス接続
- OpenAI Vision接続
- 手書きOCR
- OCR精度調整

## 6. 実行したテスト

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Streamlitもヘッドレスで起動し、HTTP応答を確認しました。

## 7. テスト結果

- pytest件数: **30件**
- 成功: **30件**
- 失敗: **0件**
- 依存関係エラー: **なし**
- Streamlit起動: **HTTP 200**
- `git diff --check`: **エラーなし**

確認済みの主な項目:

- 正常xlsxと複数シート
- Excelヘッダー、数式、結合セル
- UTF-8、UTF-8 BOM、CP932 CSV
- CSV文字コード記録と読取失敗
- テキストPDFと画像PDF
- PDFページ上限警告
- PNG、JPG、JPEG
- 画像サイズと低解像度警告
- 破損画像
- 拡張子別パーサー選択
- 対応外形式
- 指定`file_id`の解析
- 変更済みファイル版の誤解析防止
- 解析で`analysis_runs`を作成しないこと

## 8. 手動確認方法

まずStreamlitを起動します。

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

`data/upload/`へファイルを配置し、「一覧更新」で登録します。Day 3では画面から解析を自動実行しません。

開発確認では、登録済みIDを指定して解析できます。

```python
from phase0_analyzer.config import get_settings
from phase0_analyzer.file_parsing import FileParsingService
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.parsers.resolver import ParserResolver

settings = get_settings()
repository = FileRepository(settings.database_path)
service = FileParsingService(repository, ParserResolver(settings))

result = service.parse(file_id=1)
print(result)
```

## 9. 既知課題

- 登録後に同じパスの内容が変わると、旧版の原本は再解析できない
- Excelの行列数は書式だけ設定されたセルの影響を受ける可能性がある
- CSV区切り文字の自動推定に失敗する場合がある
- PDF表構造の抽出は未実装
- PDF・画像のOCR実行は未実装
- 画像のぼけ、傾き、明暗判定は未実装
- OneDrive同期中のファイル変更やSQLite競合は未検証
- AI分類、項目抽出、分析結果画面は未実装

## 10. Day 4へ進める状態か

**Day 4へ進める状態です。**

全パーサーが共通`ParseResult`を返し、形式選択、`file_id`指定、失敗時の安全な結果返却をテストできています。解析しても分析履歴が作られない境界も維持されています。

## 11. Day 4開始前に決めるべき事項

主な判断事項は、登録時に原本スナップショットを`data/original/`へ保存するかです。

現在は登録時のSHA-256と実ファイルを照合するため、内容が変更された旧版は安全に失敗します。ただし旧版そのものを再解析することはできません。

推奨方針は、Day 4で分析履歴と結び付ける前に、フェーズ0でも原本コピーを保存するか決定することです。採用する場合も外部ストレージへ広げず、`data/original/`内のローカル保存に限定します。
