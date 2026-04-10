# 顧客別納入分析システム - PyInstaller ビルドスクリプト
# 使い方: プロジェクトルート (customer_delivery_analytics) で PowerShell から実行
#   .\build_exe.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Error "PyInstaller が見つかりません。`pip install pyinstaller` 後に再実行してください。"
}

# exe 名は仕様どおり日本語（--name）
$ExeName = "顧客別納入分析システム"

pyinstaller `
    --noconfirm `
    --windowed `
    --name $ExeName `
    --pathex "$Root" `
    --collect-submodules app `
    --hidden-import pyodbc `
    --hidden-import app.config.settings `
    --hidden-import app.ui.main_window `
    --hidden-import app.ui.table_model `
    --hidden-import matplotlib.backends.backend_qtagg `
    "$Root\app\main.py"

Write-Host "完了: dist\$ExeName\$ExeName.exe を確認してください。"
