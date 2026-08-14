# Day 4実装指示 確認報告

- 確認日: 2026-08-14
- 対象: 添付された「Codex Day 4 実装指示」
- 基準: `AGENTS.md`、`docs/requirements.md`、`docs/implementation-plan.md`、Day 3実装
- 結論: **実装開始可能**

## 1. 全体評価

Day 4実装指示は、Day 3までの設計、プロジェクト要件、1週間の実装計画とおおむね整合しています。

特に、Day 3で既知課題となった「同じパスの内容が変更されると旧版を再解析できない」問題に対して、`data/original/<file_id>/<original_file_name>`へ原本スナップショットを保存する方針が明示されており、適切な解決策になっています。

また、以下の重要方針も既存要件と一致しています。

- ファイル配置だけでは分析しない
- 「一覧更新」では分析しない
- 分析サービス呼び出し時だけ分析履歴を作成する
- 再分析でも過去結果を上書きしない
- `AI_PROVIDER=mock`で外部APIなしに一連動作させる
- OCR・OpenAIの本接続を必要以上に先行実装しない
- Day 4で本格的な結果・修正画面を作らない

## 2. 実装対象の整合性

### 原本スナップショット

Day 3の`FileParsingService`は、登録時SHA-256と現在のファイルを照合し、不一致時に`FILE_VERSION_MISMATCH`を返します。この動作は誤解析防止として安全ですが、旧版の再解析はできません。

Day 4指示のスナップショット保存を追加することで、次の動作が可能になります。

1. 新規ファイル版を登録する
2. 発行された`files.id`に対応する原本を保存する
3. upload側が変更されても原本側を解析する
4. 過去ファイル版を指定`file_id`で再解析する

この方針はDay 3の`file_id`基準設計を壊さず拡張できます。

### Mock AI Provider

実AI Providerと同じPydantic結果モデルをMockでも利用する方針は適切です。UI専用のダミーデータではなく、分析サービス全体を通すため、Day 5以降も同じ契約を利用できます。

5分類は要件どおりです。

- `ORDER`
- `INVENTORY`
- `SHIPPING`
- `OTHER`
- `UNKNOWN`

### AI分析モデル

入力モデルと結果モデルに必要な情報が明示されています。Day 3の`ParseResult`から、以下を無理なく変換できます。

- `file_id`
- `file_name`
- `file_type`
- `extracted_text`
- `table_preview`
- parser metadata
- parse warnings
- `requires_ocr`

過去事例を初期段階では空配列にできる点も、Day 4の実装範囲として妥当です。

### 分析オーケストレーター

指定された処理順は、既存アーキテクチャの分離方針と一致します。

```text
file_id指定
↓
snapshot確認
↓
Parser選択
↓
ParseResult取得
↓
OCR要否確認
↓
AI分析用入力作成
↓
AI Provider実行
↓
結果検証
↓
要確認判定
↓
分析履歴・結果・項目・警告保存
```

UI、ファイル解析、OCR、AI Provider、分析調整、永続化を別モジュールに維持できます。

## 3. DBスキーマで必要な変更

現在のDBスキーマから、最低限以下の移行が必要です。

### `files`

- `original_snapshot_path`

### `analysis_runs`

- `run_number`
- `duration_ms`
- `model_name`
- `extracted_text`
- `raw_ai_response`
- `error_code`
- 必要に応じた既存列のNULL許容・既定値調整
- `(file_id, run_number)`の一意制約

### `analysis_results`

Day 4指示に従った新規テーブルが必要です。

- `analysis_run_id`
- `category_code`
- `category_label`
- `category_confidence`
- `category_reason`
- `document_type`
- `document_type_confidence`
- `provider_name`
- `target_date`
- `summary`
- `needs_review`

### `extracted_fields`

現在の列との対応を整理し、必要な列を追加します。

- `normalized_name`
- `corrected_value`
- `needs_review`
- `review_reason`

既存の`common_name`と`requires_review`を残すか、新しい名称へ段階移行するか判断が必要です。

### `warnings`

現在の`code`、`severity`、`message`を利用できます。Parser、OCR、AIの警告を同じ形式へ変換して追記します。

## 4. 事前に明確化すべき事項

### 4-1. `ai_results`と`analysis_results`

現在のスキーマには`ai_results`がありますが、Day 4指示では`analysis_results`が指定されています。

推奨方針:

- Day 4仕様に合わせて`analysis_results`を新設する
- `ai_results`は既存DB互換のため直ちに破壊的削除しない
- 将来不要と確定するまで移行対象として記録する

### 4-2. snapshotコピーとDB登録の整合性

「コピー失敗時に不完全な登録状態を残さない」ため、単純にDB登録後へ`copy`を追加するだけでは不十分です。

推奨処理:

1. DBトランザクションを開始する
2. `files.id`を発行する
3. 一時ファイルへ原本をコピーする
4. コピー先SHA-256を検証する
5. 上書きなしで正式パスへ確定する
6. `original_snapshot_path`を保存する
7. DBをコミットする
8. 失敗時はDBをロールバックし、一時ファイルを削除する

DBコミット後にファイル確定が失敗する場合も考慮し、限定されたsnapshotディレクトリだけを安全に清掃する必要があります。

### 4-3. 既存登録ファイル

既存行にsnapshotがない場合は以下とします。

- upload側SHA-256が登録値と一致: 初回解析前にsnapshotを作成可能
- SHA-256が不一致: snapshotを作らず、明示的な警告または失敗結果を返す
- 存在しないファイル: snapshotを作らず、元ファイル不在として失敗する

### 4-4. Parse失敗時のステータス

指示では要確認判定が詳しく定義されていますが、解析自体が失敗した場合の最終ステータスは明記されていません。

推奨方針:

- Parser・Providerが処理不能: `FAILED`
- 処理は完了したが確認条件に該当: `REVIEW_REQUIRED`
- 問題なく完了: `COMPLETED`

### 4-5. OCR結果なしのテスト

正常な`MockOCRProvider`だけでは「OCRが必要だが結果がない」条件を再現できません。

推奨方針:

- 通常の`MockOCRProvider`は固定テキストを返す
- テスト用に失敗または空結果を返すProviderを注入できるようにする
- OCR結果なしの場合もアプリ全体を停止せず`REVIEW_REQUIRED`へ進める

## 5. 要確認判定

指定された条件は`docs/requirements.md`と一致しています。

- 大分類信頼度が0.80未満
- 帳票種類信頼度が0.70未満
- 抽出項目に`needs_review=true`がある
- `UNKNOWN`
- `error` severityの警告がある
- OCRが必要だがOCR結果がない
- ParseResultに重大警告がある

閾値は`.env.example`に既に存在しますが、現在の`Settings`で未使用の項目はDay 4で読み込む必要があります。

ParseResultの「重大警告」は、`ParseWarning.level == "error"`を基準にするなど、コード上で明示することを推奨します。

## 6. 履歴保存方針

Day 4指示は、過去結果を上書きしない要件と一致しています。

- 分析開始ごとに`analysis_runs`へINSERT
- `file_id`単位で`run_number`を1、2、3と増加
- `analysis_results`を分析実行ごとにINSERT
- `extracted_fields`を分析実行ごとにINSERT
- `warnings`を分析実行ごとにINSERT
- 再分析でも過去行をUPDATEしない

複数行の保存は1つのDBトランザクションで行い、途中失敗による部分保存を防ぐことを推奨します。

## 7. UI範囲

Day 4指示では、必要最低限として以下を追加可能としています。

- ファイル選択
- 「分析開始」
- 処理結果ステータス表示

ただし必須の中心はサービス層です。本格的な結果詳細、修正、確定はDay 5まで実装しない方針が適切です。

## 8. テスト範囲

指示されたテスト範囲は十分です。

- snapshot作成、SHA一致、旧版解析、上書き防止、失敗時ロールバック
- Mock AIの5分類
- 初回・再分析のrun_number
- 過去分析行の保持
- 全要確認条件
- 分析実行、結果、抽出項目、警告の保存
- 配置、一覧更新、分析サービスの実行境界

追加で以下も確認することを推奨します。

- 存在しない`file_id`
- snapshotのパス外参照防止
- Providerが例外を返した場合の`FAILED`保存
- 1回の分析保存処理のトランザクション性
- APIキーなし・`AI_PROVIDER=mock`での全テスト

## 9. 対象外機能の確認

以下はDay 4でも実装対象外です。

- 本番認証
- メール自動取込
- タブレット入力
- 外部業務システム連携
- AIモデル再学習
- 本格OCR
- OpenAI API接続の必須化
- 詳細な分析結果・修正・確定画面

## 10. 最終判定

**Day 4実装指示として妥当であり、実装開始可能です。**

実装時には、特に次の3点を先に固定する必要があります。

1. `ai_results`と`analysis_results`の移行方針
2. snapshotコピーとDB登録を不完全状態にしないトランザクション設計
3. Parse不能の`FAILED`と、確認が必要な`REVIEW_REQUIRED`の区別

これらを上記推奨方針で進めれば、既存設計を壊さずDay 4の範囲を実装できます。
