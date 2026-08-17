# テスト計画

## 単体
- 新規ファイル登録
- 重複防止
- 対応外形式
- Excel読取
- 複数シート
- UTF-8 CSV
- CP932 CSV
- テキストPDF
- 画像PDF
- 正常画像
- 破損画像
- 正常AI JSON
- 不正AI JSON
- 信頼度閾値
- UNKNOWN
- Mock provider
- 分析履歴
- 修正履歴
- 確定

## 結合
1. data/uploadへ配置
2. 一覧更新
3. 一覧表示
4. 分析開始
5. 結果保存
6. 詳細表示
7. 修正
8. 修正履歴保存
9. 確定
10. CONFIRMED確認

## 業務サンプル
- 受注Excel
- 在庫CSV
- 出荷PDF
- 印字画像
- 手書き在庫確認票
- 読みにくい画像
- 対応外ファイル
- 破損ファイル

## Day 7回帰確認

- `OCR_REVIEW_REQUIRED=true`でOCR対象が`REVIEW_REQUIRED`になる
- `OCR_REVIEW_REQUIRED=false`で暫定ルールを解除できる
- AI入力の列数が`AI_MAX_COLUMNS`以内になる
- AI入力の合計文字数が`AI_MAX_INPUT_CHARS`以内になる
- 上限適用時に`AI_INPUT_TRUNCATED`が保存される
- Parser元結果とDB保存全文が切り詰められない
- 一覧に最新AI分類、最新帳票種類、要確認件数、最新run、詳細表示が出る
- JPEGの分析、要確認、元画像表示をStreamlitで確認する
- 横長XLSXの制限警告、代表列表示、修正、確定をStreamlitで確認する

## フェーズ0検証版の最終確認

- 未分析、分析中、分析済み、要確認、確認済み、エラーの日本語状態と次操作
- 同じ警告コードを要確認件数へ重複計上しない
- 一覧と結果画面の要確認件数が一致する
- 分析開始日時、完了日時、`duration_ms`の秒表示
- 通常画面にconfidence、run番号、Provider、model、Parser metadataを出さない
- 未分析から分析開始、Excel結果表示、JPEG要確認と元画像、修正から確定を確認する
