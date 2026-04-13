# Customer Delivery Analytics - PyInstaller build script
#
# 既定: 単一 exe（配布は dist\顧客別納入分析システム.exe のみで可。実行時は一時フォルダに展開）
# フォルダ配布でデバッグする場合:  $env:CDA_FOLDER = "1"; .\build_exe.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Error 'PyInstaller was not found. Run pip install pyinstaller and retry.'
}

$ExeName = '顧客別納入分析システム'
$IconPng = Join-Path $Root 'docs\icon.png'
$IconIco = Join-Path $Root 'docs\icon.ico'
# 単一 exe を既定とし、明示的に CDA_FOLDER=1 のときだけ onedir
$BuildOneFile = $env:CDA_FOLDER -ne '1'

$RthookDateutil = Join-Path $Root 'pyi_rth_cda_dateutil.py'
if (-not (Test-Path -LiteralPath $RthookDateutil)) {
    Write-Error "Runtime hook not found: $RthookDateutil"
}

$PyInstallerArgs = @(
    '--noconfirm',
    '--windowed',
    '--name', $ExeName,
    '--specpath', (Join-Path $Root 'build\pyi_spec'),
    '--workpath', (Join-Path $Root 'build\pyi_work'),
    '--runtime-hook', $RthookDateutil,
    '--paths', "$Root",
    '--collect-submodules', 'app',
    '--hidden-import', 'pyodbc',
    '--hidden-import', 'app.config.settings',
    '--hidden-import', 'app.ui.main_window',
    '--hidden-import', 'app.ui.table_model',
    '--hidden-import', 'matplotlib.backends.backend_qtagg',
    '--add-data', "$IconPng;docs"
)

if (Test-Path $IconIco) {
    $PyInstallerArgs += @('--icon', $IconIco)
}

if ($BuildOneFile) {
    $PyInstallerArgs += @('--onefile', '--clean')
}

$PyInstallerArgs += "$Root\app\main.py"

pyinstaller @PyInstallerArgs

if ($BuildOneFile) {
    Write-Host ('Done (onefile): dist\{0}.exe only - no extra files required beside the .exe.' -f $ExeName)
} else {
    Write-Host ('Done (folder): dist\{0}\{0}.exe - distribute the whole folder.' -f $ExeName)
}
