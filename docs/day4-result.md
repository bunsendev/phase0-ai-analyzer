# 4日目 作業結果

## 実施したこと

- file_id単位の原本snapshot保存とSHA-256検証
- 既存登録行の安全なsnapshot補完
- Mock OCR Provider
- PydanticによるAI入力・結果モデル
- 5分類対応のMock AI Provider
- 要確認判定
- AnalysisServiceと分析履歴の追記保存
- 最小のファイル選択・分析開始・ステータス表示UI
- Day 4 DBスキーマ移行

## DBスキーマ

- `files.original_snapshot_path`
- `analysis_runs`: run_number、duration、provider/model、解析・AI生データ、エラー
- `analysis_results`新設
- `extracted_fields`: normalized/corrected/review列
- `(file_id, run_number)`一意インデックス

## 動作境界

- 配置だけでは分析しない
- 一覧更新ではsnapshot登録だけを行い、分析しない
- 「分析開始」またはAnalysisService直接呼び出し時だけrunを追加する
- 再分析はrun_numberを増やし、過去runを保持する

## テスト結果

- `python -m pytest`: 44件成功
- `python -m pip check`: 依存関係エラーなし
- Streamlit実サーバー: HTTP 200
- Streamlit操作テスト: 登録→分析開始→履歴1件→COMPLETED更新に成功
- `git diff --check`: エラーなし

## 未実装

- 実OCR、OpenAI API、Vision
- 詳細結果、修正、確定UI
- 類似帳票検索、過去事例再利用
- AIモデル再学習、外部連携
