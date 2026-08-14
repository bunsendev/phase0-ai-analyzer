# Day 4完了報告書

- 更新日: 2026-08-14
- 基準文書: `AGENTS.md`、`docs/requirements.md`、`docs/implementation-plan.md`
- 現在地点: Day 4完了、Day 5着手可能

## 1. 変更ファイル

### 主な新規モジュール

- `src/phase0_analyzer/snapshot.py`
- `src/phase0_analyzer/ai_models.py`
- `src/phase0_analyzer/ai_provider.py`
- `src/phase0_analyzer/analysis_service.py`
- `src/phase0_analyzer/analysis_repository.py`
- `src/phase0_analyzer/review.py`

### 主な更新モジュール

- `src/phase0_analyzer/database.py`
- `src/phase0_analyzer/config.py`
- `src/phase0_analyzer/file_repository.py`
- `src/phase0_analyzer/file_registration.py`
- `src/phase0_analyzer/file_parsing.py`
- `src/phase0_analyzer/ocr_provider.py`
- `src/phase0_analyzer/ui/home.py`
- `pyproject.toml`

### 新規テスト

- `tests/test_snapshot.py`
- `tests/test_mock_ai.py`
- `tests/test_review.py`
- `tests/test_analysis_service.py`

### 文書

- `README.md`
- `docs/decisions.md`
- `docs/known-issues.md`
- `docs/day4-result.md`

## 2. DBスキーマ変更

スキーマバージョンを3へ更新しました。既存DBから移行できます。

### `files`

- `original_snapshot_path`

### `analysis_runs`

- `run_number`
- `duration_ms`
- `model_name`
- `extracted_text`
- `raw_ai_response`
- `error_code`
- `(file_id, run_number)`の一意インデックス

### `analysis_results`

分析実行ごとの結果を保存するテーブルとして新設しました。

- 大分類コード、ラベル、信頼度、理由
- 帳票種類と信頼度
- 提供元
- 対象日
- 要約
- 要確認状態

### `extracted_fields`

- `normalized_name`
- `corrected_value`
- `needs_review`
- `review_reason`

旧`ai_results`テーブルは既存DB互換のため残しています。Day 4の保存処理は`analysis_results`を使用します。

## 3. 原本snapshot保存

新規ファイル版の登録時に、次のパスへ原本を保存します。

```text
data/original/<file_id>/<元ファイル名>
```

処理順:

1. DBトランザクションを開始
2. `files.id`を発行
3. コピー元SHA-256を再確認
4. 一時ファイルへコピー
5. コピー先SHA-256を検証
6. 上書きなしで正式パスへ確定
7. `original_snapshot_path`を保存
8. DBをコミット

コピーやSHA検証に失敗した場合はDB登録をロールバックし、不完全な一時ファイルやsnapshotを削除します。

既存登録行にsnapshotがない場合は、upload側のSHA-256が登録値と一致するときだけ解析前に補完します。不一致の場合は勝手にsnapshotを作成しません。

解析は原則としてsnapshot側を使用するため、upload側が後から変更されても登録済みの旧版を解析できます。

## 4. MockOCRProvider

Day 3の`OCRProvider` Protocolを利用する`MockOCRProvider`を追加しました。

- `requires_ocr=false`: OCR Providerを呼ばない
- `requires_ocr=true`: Mock OCRを呼び、固定テキストを返す
- 失敗するOCR Providerも注入可能
- OCR失敗時はerror警告を保存
- OCR結果がない場合は`REVIEW_REQUIRED`

実OCR、手書きOCR、OpenAI Visionは実装していません。

## 5. AI ProviderとPydanticモデル

### 入力

`AnalysisRequest`には以下を含みます。

- file ID、名前、形式
- Parser抽出テキスト
- table preview
- Parser metadata、警告
- OCRテキストとOCR要否
- 過去事例用の空配列

### 結果

`AIAnalysisResult`には以下を含みます。

- 大分類
- 帳票種類
- 提供元
- 対象日
- 抽出項目
- 要約
- 警告
- 要確認状態

ProviderはこのPydanticモデルを返します。

## 6. MockAIProvider

簡易キーワードルールで5分類を返します。

- 受注、注文、order → `ORDER`
- 在庫、棚卸、inventory、stock → `INVENTORY`
- 出荷、配送、送り状、shipping → `SHIPPING`
- 内容はあるが既知キーワードなし → `OTHER`
- 内容なし → `UNKNOWN`

Mock固有の分類処理はUIへ置かず、Provider内部に閉じ込めています。

## 7. AnalysisService

明示的な分析開始操作からだけ呼ばれるサービスです。

```text
file_id取得
↓
ファイルステータスをANALYZINGへ更新
↓
snapshot確認
↓
Parser実行
↓
必要時Mock OCR
↓
AnalysisRequest作成
↓
Mock AI実行
↓
要確認判定
↓
分析履歴・結果・項目・警告を保存
↓
COMPLETED / REVIEW_REQUIRED / FAILEDへ更新
```

ファイル配置や「一覧更新」では呼ばれません。

## 8. 分析履歴

分析開始ごとに新しい`analysis_runs`行を追加します。

- 初回: `run_number=1`
- 再分析: `run_number=2`
- 以降: 3、4、5と増加

既存runは更新しません。結果、抽出項目、警告も分析実行ごとに新しい行として保存します。

以下は1つのDBトランザクションで保存します。

- `analysis_runs`
- `analysis_results`
- `extracted_fields`
- `warnings`

## 9. 要確認判定

以下のいずれかで`REVIEW_REQUIRED`になります。

- 大分類confidenceが0.80未満
- 帳票種類confidenceが0.70未満
- 抽出項目に`needs_review=true`
- `UNKNOWN`分類
- severityが`error`の警告
- OCR必須だがOCR結果なし
- Parserの重大警告

処理不能の場合は`FAILED`、問題がなければ`COMPLETED`です。

## 10. 最小UI

Day 4の範囲として次を追加しました。

- `READY`ファイルの選択
- 「分析開始」ボタン
- 分析後のステータス表示

詳細結果、修正、確定画面は実装していません。

## 11. テスト結果

実行コマンド:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

結果:

- pytest件数: **44件**
- 成功: **44件**
- 失敗: **0件**
- 依存関係エラー: **なし**
- `git diff --check`: **エラーなし**

## 12. Streamlit確認結果

- 実サーバー起動: **HTTP 200**
- Streamlit操作テスト:
  1. ファイル配置のみでは分析履歴0件
  2. 「一覧更新」後も分析履歴0件
  3. 「分析開始」後に分析履歴1件
  4. ファイルステータスが`COMPLETED`へ更新

## 13. 仕様遵守

- ファイル配置だけでは分析しない: **遵守**
- 一覧更新では分析しない: **遵守**
- 分析開始時だけ履歴を作成する: **遵守**
- 原本を上書きしない: **遵守**
- 過去分析結果を上書きしない: **遵守**
- `AI_PROVIDER=mock`で動作する: **確認済み**
- APIキーなしでテスト可能: **確認済み**
- 実OCR・OpenAI接続を追加しない: **遵守**
- 本番認証・外部連携・自動取込を追加しない: **遵守**

## 14. 既知課題

- Mock OCRは固定テキストで、OCR精度を評価するものではない
- Mock AIは簡易キーワード分類で、実データ精度を評価するものではない
- snapshotとDBをまたぐため、OS強制終了時の孤立一時ファイル回収は未実装
- run_number採番は単一利用者プロトタイプ向け
- OneDrive同期中のファイル・SQLite競合は未検証
- 旧`ai_results`テーブルが互換性のため残っている
- 詳細結果表示、修正、確定、類似帳票検索は未実装
- 現在の成果物には未コミットの変更が含まれる

## 15. Day 5へ進める状態か

**Day 5へ進める状態です。**

snapshotからParser、Mock OCR、Mock AI、要確認判定、履歴保存、ステータス更新まで一連動作し、再分析時に過去runを残すことも確認できています。

## 16. Day 5開始前に決めるべき事項

1. 詳細画面で最新runを初期表示するか、過去runを選択可能にするか
2. 修正値をAI結果へ直接書かず、修正履歴と確定結果から表示合成する方針
3. 確定後も元のAI結果を不変に保つ方針
4. `CONFIRMED`後の再分析を許可するか
5. error警告を利用者が確認済みにできるか

推奨方針は、AI分析結果を不変に保ち、修正・確定を別の追記テーブルとして保存する方式です。
