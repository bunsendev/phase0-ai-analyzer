# Project Instructions

## Goal
Build a one-week prototype that:
- reads files from one shared upload directory,
- starts analysis only when the user presses an analysis button,
- parses spreadsheets, PDFs and images,
- uses OCR/AI to classify and extract content,
- displays results,
- allows corrections,
- preserves all analysis and correction history.

The project also teaches internal developers the full development process.

## Scope
Implement only `docs/requirements.md`.

Do not add:
- automatic email ingestion,
- automatic analysis on file placement,
- production authentication,
- external system integration,
- tablet field-entry screens,
- model fine-tuning,
- production-scale infrastructure.

## Architecture
Separate:
- UI
- file discovery
- file parsing
- OCR/AI provider
- analysis orchestration
- persistence
- correction history

The app must work with `AI_PROVIDER=mock`.

## Quality
- Python type hints
- pytest for core services
- no secrets in Git
- no business source files in Git
- Japanese user-facing errors
- never overwrite prior analysis
- never overwrite correction history
- update `docs/decisions.md` when behavior decisions change
- update `docs/known-issues.md` for unfinished items

## Completion
Before completing a task:
1. Run tests.
2. Verify app startup.
3. Verify the relevant user flow.
4. Update known issues.
5. Report changed files and test results.
