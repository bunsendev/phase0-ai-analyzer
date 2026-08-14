# 文書の役割

## Codexが必ず読む
- `AGENTS.md`: 開発ルール
- `docs/requirements.md`: 主仕様書

## 開発担当者が読む
- `README.md`: 全体概要
- `docs/implementation-plan.md`: 1週間の順序
- `docs/test-plan.md`: 確認方法
- `docs/day1-guide.md`: 初日手順

## 日々更新
- `docs/decisions.md`: 判断理由
- `docs/known-issues.md`: 未解決事項
- `docs/dayX-result.md`: 日次結果

## 報告書ファイル名の統一
- 日次の正式報告書は`docs/dayN-result.md`とする（例: `docs/day6-result.md`）
- 同じDayの追加検証・修正報告も正式報告書へ追記し、別名の報告書を新規作成しない
- `progress-report-*.md`および`progress-report-day*-*.md`は旧形式として保持するが、今後は更新・追加しない
- 検証管理表、要件、判断記録、既知課題は報告書ではないため、それぞれ既存の専用ファイル名を使用する

## Codexへ貼る
- `docs/codex-first-prompt.md`
- `docs/codex-task1-prompt.md`

## 更新原則
- 挙動変更 → requirements
- 判断変更 → decisions
- 未完成/不具合 → known-issues
- 日次作業・追加報告 → dayN-result
