# ローカルUI起動・テスト手順

## 目的

業務担当者がStreamlit UIへアクセスし、フェーズ0の4ケースを確認できる環境を再現する。通常操作は「ファイル登録、分析開始、結果確認」の3ステップだけとし、ファイル配置だけでは分析しない。

## 1. 現在の端末状態

2026-08-16時点で、現在の`.venv`はCodex同梱Python 3.12.13から作成されている。Windows Code Integrityログのイベント3033・3077により、次がWDAC（App Control for Business）Policy ID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`で拒否されている。

- `.venv/Scripts/python.exe`: Enterprise signing level要件を満たさない
- Codex同梱Pythonの`libssl-3-x64.dll`: Enterprise signing level要件を満たさない

PowerShellの実行ポリシーは`LocalMachine=RemoteSigned`であり、今回の拒否原因ではない。`Set-ExecutionPolicy`や`Unblock-File`ではWDACポリシーを解消できないため実行しない。

参考:

- [Microsoft: App Control debugging and troubleshooting](https://learn.microsoft.com/windows/security/application-security/application-control/app-control-for-business/operations/appcontrol-debugging-and-troubleshooting)
- [Microsoft: App Control event tags](https://learn.microsoft.com/windows/security/application-security/application-control/app-control-for-business/operations/event-tag-explanations)
- [Python: Using Python on Windows](https://docs.python.org/3/using/windows.html)

## 2. 推奨する環境配置

| 対象 | 推奨場所 | 理由 |
|---|---|---|
| ソースコード | 現在のGitリポジトリ | Git管理を維持する |
| Python | 社内管理者が許可したPython 3.11以上 | WDACに適合させる |
| 仮想環境 | `%LOCALAPPDATA%/Phase0AIAnalyzer/.venv` | OneDrive同期対象から外す |
| SQLite | `%LOCALAPPDATA%/Phase0AIAnalyzer/database/phase0.db` | OneDrive同期競合を避ける |
| snapshot | `%LOCALAPPDATA%/Phase0AIAnalyzer/original` | DBと同じローカル領域で管理する |
| 一時作業 | `%LOCALAPPDATA%/Phase0AIAnalyzer/work` | OneDrive同期対象から外す |
| 通常ファイル | `data/upload/` | 現在の手動登録フローを維持する |
| 実データ検証 | `data/validation/actual/` | Git対象外の検証導線を維持する |

ソース、実データ、旧DB、旧snapshotは削除しない。新しいローカルDBは検証用として空の状態から開始し、画面の明示操作で再登録する。

## 3. WDAC対応

### 管理端末の場合

管理者へ次を伝え、社内で許可されたPythonをインストールまたは許可してもらう。

```text
用途: ローカルStreamlitプロトタイプのpytest・UI確認
必要バージョン: Python 3.11以上
拒否イベント: CodeIntegrity 3033 / 3077
Policy ID: {0283ac0f-fff1-49ae-ada1-8a933130cad6}
拒否対象: 現在の未署名venv python.exeとCodex同梱libssl-3-x64.dll
希望: 社内承認済みPython配布、または承認済み署名・ハッシュ・発行元ルール
```

WDACポリシー自体を無効化せず、管理者が承認したPythonを使用する。

### Python許可後の確認

新しいPowerShellを開き、次を実行する。

```powershell
Get-Command python
python --version
Get-AuthenticodeSignature (Get-Command python).Source |
    Select-Object Status, StatusMessage
```

`python --version`が成功してから次へ進む。WindowsAppsのインストール案内だけが表示される場合、Python本体は未導入である。

## 4. 仮想環境の再構築

現在の`.venv`はすぐに削除せず、承認済みPythonの動作確認後に退避する。

```powershell
Set-Location "C:\Users\zept0\OneDrive\ドキュメント\GitHub\phase0-ai-analyzer"

$runtimeRoot = Join-Path $env:LOCALAPPDATA "Phase0AIAnalyzer"
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

python -m venv (Join-Path $runtimeRoot ".venv")
$pythonExe = Join-Path $runtimeRoot ".venv\Scripts\python.exe"

& $pythonExe --version
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -e ".[dev]"
```

依存関係確認:

```powershell
& $pythonExe -m pip check
& $pythonExe -m pytest
```

## 5. 検証用`.env`

`.env`がない場合だけ作成する。

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

`.env`の次の3項目を、実際のユーザー名を含む絶対パスへ変更する。

```dotenv
ORIGINAL_DIR=C:/Users/zept0/AppData/Local/Phase0AIAnalyzer/original
WORK_DIR=C:/Users/zept0/AppData/Local/Phase0AIAnalyzer/work
DATABASE_URL=sqlite:///C:/Users/zept0/AppData/Local/Phase0AIAnalyzer/database/phase0.db
```

次は維持する。

```dotenv
UPLOAD_DIR=./data/upload
VALIDATION_DIR=./data/validation/actual
AI_PROVIDER=mock
OCR_REVIEW_REQUIRED=true
AI_MAX_COLUMNS=100
AI_MAX_INPUT_CHARS=100000
```

`.env`、DB、snapshot、実データはGit管理対象外である。旧DBを新DBへ単純コピーすると、DB内のsnapshot絶対パスが旧保存先を指すため行わない。検証用ファイルを画面から再登録する。

## 6. Streamlitの起動とアクセス

```powershell
Set-Location "C:\Users\zept0\OneDrive\ドキュメント\GitHub\phase0-ai-analyzer"
$pythonExe = Join-Path $env:LOCALAPPDATA "Phase0AIAnalyzer\.venv\Scripts\python.exe"

& $pythonExe -m streamlit run app.py --server.address localhost --server.port 8501
```

ターミナルにURLが表示されたら、ブラウザで次へアクセスする。

```text
http://localhost:8501
```

別のPowerShellから起動確認する場合:

```powershell
Invoke-WebRequest http://localhost:8501/_stcore/health |
    Select-Object StatusCode, Content
```

`StatusCode=200`、`Content=ok`なら起動している。終了はStreamlitを起動したPowerShellで`Ctrl+C`を押す。

## 7. UIの4ケース確認

### ケース1: 未分析から分析開始

1. `data/validation/actual/`にある対応形式を1件選ぶ。
2. 「検証用ファイルを使用する」を開く。
3. 「検証ファイルを読み取る」を押す。
4. 状態「未分析」と主操作「分析開始」を確認する。
5. ファイル配置・登録だけでは分析履歴が作られないことを確認する。
6. 「分析開始」を押す。

### ケース2: Excelの結果表示

1. XLSXを選ぶ。
2. 「分析開始」を押す。
3. 「分析結果」「主な内容」「元データ」が表示されることを確認する。
4. 横長ExcelではAI入力制限警告と代表列表示を確認する。
5. 「詳細情報（開発・調査用）」で開始日時、完了日時、分析時間を確認する。

### ケース3: JPEGの要確認と元画像

1. JPEGを選んで分析する。
2. 状態「要確認」と要確認件数を確認する。
3. 「画像・手書き帳票のため、OCR結果を確認してください。」を確認する。
4. 元画像が表示されることを確認する。

### ケース4: 修正、確定、確認済み

1. 結果の任意項目を修正する。
2. 「修正内容を保存」を押す。
3. 「結果を確定」を押す。
4. 状態「確認済み」と案内「担当者による確認が完了しています。」を確認する。
5. 過去のAI元結果と修正履歴が残ることを確認する。

結果と操作時間は`docs/operator-validation-result.md`へ記録する。

## 8. テスト完了チェック

```powershell
& $pythonExe -m pytest
& $pythonExe -m pip check
git diff --check
```

- [ ] pytestが全件成功した
- [ ] pip checkが`No broken requirements found.`になった
- [ ] git diff --checkが終了コード0になった
- [ ] Streamlit health checkが200になった
- [ ] UIの4ケースを確認した
- [ ] 担当者検証結果を記録した

## 9. よくある問題

### `python`を実行するとMicrosoft Storeが開く

Python本体がインストールされていない。社内承認済みのPythonを導入する。

### 「アプリケーション制御ポリシーによってブロックされました」

WDACの拒否であり、PowerShell実行ポリシーの問題ではない。Code Integrityイベント3033・3077を確認し、管理者へ許可を依頼する。

### ポート8501が使用中

```powershell
Get-NetTCPConnection -LocalPort 8501 -State Listen
```

既存のStreamlitを終了するか、`--server.port 8502`で起動する。

### DBを初期化して再検証したい

現在のDBは削除しない。`.env`の`DATABASE_URL`を新しいファイル名へ変更し、空の検証DBとして開始する。

