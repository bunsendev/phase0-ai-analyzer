# 3日目 作業結果

## 実施したこと

- `BaseParser`、`ParseResult`、`ParseWarning`、`ParseError`の共通解析モデル
- Excel、CSV、PDF、画像パーサー
- 拡張子による`ParserResolver`
- `files.id`を基準に解析する`FileParsingService`
- 登録済みSHA-256によるファイル版照合
- OCR ProviderのProtocol境界
- パーサー依存関係と自動テスト

## 各パーサー

### Excel

- シート名、行列数、ヘッダー候補、先頭100行
- 数式、結合セル、空白行、空白列
- 全シート合計で最大30行の`table_preview`

### CSV

- UTF-8、UTF-8 BOM、CP932、Shift_JISの順で読込
- 使用文字コード、区切り文字、行列数、ヘッダー、先頭100行
- 列数不一致と区切り文字フォールバックの警告

### PDF

- 最大ページ数までのテキスト抽出
- ページ数、解析ページ数、抽出文字数、テキスト・画像PDF判定
- 閾値未満の`requires_ocr=true`
- ページ上限超過の警告

### 画像

- PNG、JPG、JPEGの幅、高さ、形式、ファイルサイズ
- 原則`requires_ocr=true`
- 500px未満と破損画像の警告

## 実装しなかったこと

- OCR実行
- OpenAI API接続
- AI分類、項目抽出
- 分析実行履歴の作成
- 分析結果画面

## テスト結果

- `python -m pytest`: 30件成功
- 失敗: 0件
- `python -m pip check`: 依存関係エラーなし
- Streamlit起動確認: HTTP 200
- `git diff --check`: エラーなし

## 既知課題

- `docs/known-issues.md`を参照
- 過去版のバイト列を再解析するには原本スナップショット方針の決定が必要

## 次に行うこと

- Day 4: AI JSONスキーマ、Pydantic検証、Mock AI Provider、分類・項目抽出
