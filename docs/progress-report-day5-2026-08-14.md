# Day 5完了報告書

- 更新日: 2026-08-14
- 基準文書: `AGENTS.md`、`docs/requirements.md`、`docs/implementation-plan.md`
- 現在地点: Day 5完了、Day 6の実データ検証へ移行可能

## 1. 変更ファイル

### 新規

- `src/phase0_analyzer/result_service.py`
- `tests/test_result_service.py`
- `docs/day5-result.md`

### 主な更新

- `src/phase0_analyzer/database.py`
- `src/phase0_analyzer/ui/home.py`
- `tests/test_database.py`
- `tests/test_app_startup.py`
- `README.md`
- `docs/decisions.md`
- `docs/known-issues.md`

## 2. DBスキーマ変更

スキーマバージョンを4へ更新しました。既存DBから移行できます。

### `correction_history`

以下の対象識別列を追加しました。

- `file_id`
- `analysis_result_id`
- `target_type`
- `target_id`

### `confirmed_results`

以下を追加しました。

- `file_id`
- `analysis_result_id`
- `confirmed_category_code`
- `confirmed_document_type`
- `confirmed_provider_name`
- `confirmed_target_date`

### `confirmed_fields`

項目単位の確定値を保存するテーブルとして新設しました。

- `confirmed_result_id`
- `extracted_field_id`
- `normalized_name`
- `confirmed_value`

## 3. 3層のデータ分離

Day 5では、以下を別々に保持します。

```text
AIが出した元結果
  analysis_results / extracted_fields

担当者が修正した履歴
  correction_history

最終的に確定した結果
  confirmed_results / confirmed_fields
```

以下のAI元データは修正・確定時にも更新しません。

- `analysis_results`
- `extracted_fields.extracted_value`
- confidence
- AI reason
- raw AI response

## 4. 詳細結果画面

ファイル一覧の下に分析結果詳細を追加しました。

表示内容:

- ファイルとrunの選択
- run number、分析日時、AI Provider、model name
- AI大分類、信頼度、分類理由
- 帳票種類、提供元、対象日
- AI要約
- warning一覧
- extracted fields
- 確定日時、確定者
- 元データの簡易プレビュー

初期表示は最新runです。run number降順で過去runも選択できます。

## 5. 元データプレビュー

- CSV・Excel: 最大50行程度の表形式プレビュー
- PDF: 抽出テキスト
- PNG・JPG・JPEG: 原本snapshot画像

高度なPDFページ画像化、OCR座標、領域ハイライトは実装していません。

## 6. 要確認項目の優先表示

詳細画面上部に以下をまとめて表示します。

- 分析結果の`needs_review`
- `UNKNOWN`分類
- warning
- `needs_review=true`の抽出項目

問題がない場合は、修正せずそのまま確定できることを表示します。警告と元データは折りたたみ表示にしています。

## 7. 修正可能項目

- 大分類
- 帳票種類
- 提供元
- 対象日
- extracted fieldの値
- normalized name

confidence、AI reason、raw response、Parser metadataは修正できません。

## 8. 修正履歴の保存

「修正内容を保存」押下時に、画面入力と現在値を比較します。

- 実際に変更された項目だけINSERT
- 変更なしなら履歴0件
- 同じ項目を再修正しても過去履歴を削除しない
- 変更前後、対象、修正者、修正日時を保存
- AI元結果は更新しない

## 9. 現在値の合成

表示時に以下を合成します。

```text
AI元結果
＋
target_type・target_id単位の最新修正
＝
現在値
```

例:

```text
AI元結果: ORDER
最新修正: SHIPPING
現在値: SHIPPING
```

通常は現在値を入力欄へ表示し、AI元分類、confidence、reasonは補足表示します。

## 10. 確定処理

「結果を確定」押下時に、AI元結果と最新修正を合成した状態をsnapshotとして保存します。

- 主要値: `confirmed_results`
- 項目値: `confirmed_fields`
- ファイル状態: `CONFIRMED`
- 確定日時と確定者を保存

複数回確定しても過去の確定結果を削除・更新しません。

## 11. CONFIRMED後の再分析

確定済みファイルも「分析開始」の対象にできます。

再分析時:

- 新しい`analysis_run`を追加
- run numberを増加
- 過去runを保持
- 過去修正履歴を保持
- 過去確定結果を保持
- 新しいAI結果で旧確定結果を自動更新しない

最新AI分析と既存確定結果は別データとして扱います。

## 12. 過去run表示

run number降順で表示し、最新runを初期選択します。

過去runを選択すると、そのrunに属する以下を表示します。

- AI分析結果
- 抽出項目
- warning
- 修正履歴を反映した現在値
- 確定結果

## 13. 担当者負担軽減

- 要確認理由を画面上部へ集約
- 問題がなければそのまま確定可能
- AI元結果は補足表示
- warningと元データは折りたたみ可能
- 変更された項目だけ保存
- 修正保存と確定を別操作に分離
- 日本語エラーを維持

## 14. テスト結果

実行コマンド:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

結果:

- pytest件数: **47件**
- 成功: **47件**
- 失敗: **0件**
- 依存関係エラー: **なし**
- `git diff --check`: **エラーなし**

主な確認項目:

- 分類、帳票種類、項目値、normalized nameの修正
- 同じ項目の複数回修正
- 過去修正履歴の保持
- AI元結果の不変性
- 変更なしで履歴を作らないこと
- 最新修正の現在値反映
- 修正なし・修正ありの確定
- `CONFIRMED`更新
- 確定後の再分析
- run number増加
- 過去runと過去確定結果の保持

## 15. Streamlit確認結果

- 実サーバー起動: **HTTP 200**
- Streamlit操作テスト:
  1. ファイル登録
  2. 分析開始
  3. 詳細表示
  4. 分類修正
  5. 修正履歴保存
  6. AI元分類が不変であることを確認
  7. 結果確定
  8. `CONFIRMED`更新
  9. 再分析
  10. runが2件へ増加
  11. 旧確定結果が残ることを確認

## 16. 既知課題

- warningの確認済み状態は未実装
- 確定取消、確定版同士の比較UIは未実装
- 元データプレビューは簡易版
- OCR座標、PDFページ画像は未表示
- 修正者・確定者は`DEFAULT_USER`固定
- 日時とconfidenceの表示整形は最小限
- OneDrive同期中の競合は未検証
- 実OCR、OpenAI API、類似帳票検索は未実装
- 現在の成果物には未コミットの変更が含まれる

## 17. Day 6へ進める状態か

**Day 6へ進める状態です。**

ファイル登録、分析、詳細確認、修正、確定、再分析、履歴保持まで一連の利用者フローが成立しています。

## 18. Day 6で準備すべきもの

Gitへ追加しないローカル業務サンプルとして、以下を準備します。

- 受注Excel
- 在庫CSV
- 出荷PDF
- 画像PDF
- 印字画像
- 手書き帳票画像
- 低解像度、傾き、暗い画像
- 複数シートExcel
- CP932 CSV
- 対応外ファイル
- 破損ファイル

各サンプルについて、期待する分類、帳票種類、抽出項目、要確認条件を簡単に記録しておくと検証しやすくなります。
