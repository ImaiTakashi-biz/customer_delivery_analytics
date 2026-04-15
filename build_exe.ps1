# Customer Delivery Analytics - PyInstaller build script

#

# 既定: onedir（dist\顧客別納入分析システム\ に展開される。起動が速く、exe 本体も小さい）

# 単一 exe が必要な場合:  $env:CDA_ONEFILE = "1"; .\build_exe.ps1



$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot

Set-Location $Root



if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {

    Write-Error 'PyInstaller was not found. Run pip install pyinstaller and retry.'

}



$ExeName = '顧客別納入分析システム'

$IconPng = Join-Path $Root 'docs\icon.png'

$IconIco = Join-Path $Root 'docs\icon.ico'

# 既定は onedir。明示的に CDA_ONEFILE=1 のときだけ onefile

$BuildOneFile = $env:CDA_ONEFILE -eq '1'


$RthookDateutil = Join-Path $Root 'pyi_rth_cda_dateutil.py'

if (-not (Test-Path -LiteralPath $RthookDateutil)) {

    Write-Error "Runtime hook not found: $RthookDateutil"

}



# scipy / sklearn は予測ロジックで未使用（numpy の加重 lstsq のみ）。同梱すると exe が肥大化するため除外する。

$PyInstallerArgs = @(

    '--noconfirm',

    '--windowed',

    '--name', $ExeName,

    '--specpath', (Join-Path $Root 'build\pyi_spec'),

    '--workpath', (Join-Path $Root 'build\pyi_work'),

    '--runtime-hook', $RthookDateutil,

    '--paths', "$Root",

    '--collect-submodules', 'app',

    '--exclude-module', 'scipy',

    '--exclude-module', 'sklearn',

    '--exclude-module', 'pytest',

    '--exclude-module', 'pyarrow',

    '--exclude-module', 'certifi',

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



# MSVC ランタイム DLL を明示同梱（配布先で VC++ 再頒布可が無い環境向け）

$PyPrefix = (python -c "import sys; print(sys.base_prefix)" 2>$null)

if (-not $PyPrefix) {

    Write-Error 'Python が見つからず、ランタイム DLL パスを解決できません。'

}

$PyPrefix = $PyPrefix.Trim()

$RuntimeDllsToBundle = @(

    (Join-Path $PyPrefix 'vcruntime140.dll'),

    (Join-Path $PyPrefix 'vcruntime140_1.dll')

)

$PySideDir = (python -c "import os, PySide6; print(os.path.dirname(PySide6.__file__))" 2>$null)

if ($PySideDir) {

    $PySideDir = $PySideDir.Trim()

    $RuntimeDllsToBundle += (Join-Path $PySideDir 'msvcp140.dll')

}

foreach ($dllPath in $RuntimeDllsToBundle) {

    if (Test-Path -LiteralPath $dllPath) {

        $PyInstallerArgs += @('--add-binary', "${dllPath};.")

        Write-Host "Bundling runtime DLL: $dllPath"

    } else {

        Write-Warning "Runtime DLL not found (skipped): $dllPath"

    }

}



if ($BuildOneFile) {

    $PyInstallerArgs += '--onefile'
}
$PyInstallerArgs += '--clean'



$PyInstallerArgs += "$Root\app\main.py"



pyinstaller @PyInstallerArgs



if ($BuildOneFile) {

    Write-Host ('Done (onefile): dist\{0}.exe only - no extra files required beside the .exe.' -f $ExeName)

} else {

    Write-Host ('Done (folder): dist\{0}\{0}.exe - distribute the whole folder.' -f $ExeName)

}
