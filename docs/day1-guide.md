# 初めての人向け 今日の作業手順

## 今日のゴール
- GitHubで管理開始
- Codexが仕様を読める
- 最小アプリが起動
- 作業結果を記録

## Step 1 サンプルを準備
5〜10件程度。
受注、在庫、出荷配送、Excel、CSV、PDF、手書き画像。
`data/upload/` に入れる。
業務データはGitHubへpushしない。

## Step 2 GitHub Desktop
1. GitHub Desktop起動
2. New repository
3. Name: `phase0-ai-analyzer`
4. Local path指定
5. PrivateでPublish
6. `.gitignore`確認

## Step 3 文書配置
直下:
- README.md
- AGENTS.md
- .gitignore
- .env.example

docs:
- requirements.md
- implementation-plan.md
- test-plan.md
- decisions.md
- known-issues.md

## Step 4 Codexへ最初の指示
`docs/codex-first-prompt.md` を貼る。

## Step 5 Codex計画確認
含める:
- Streamlit
- SQLite
- ファイル一覧
- 分析開始
- parser
- Mock AI
- 結果画面
- 修正・確定
- test

外す:
- メール自動取得
- タブレット
- 本番認証
- 外部連携
- モデル再学習

## Step 6 タスク1実装
`docs/codex-task1-prompt.md` を貼る。

## Step 7 自分で起動
READMEに従って起動。

## Step 8 GitHub Desktopで差分確認
Changes → 差分確認 → `.env`や業務データがないか確認 → Commit → Push。

推奨コミット:
`Initial phase0 project setup`

## Step 9 結果記録
`docs/day1-result-template.md` をコピーし、`docs/day1-result.md` として記録。
