# Customer Delivery Analytics - PyInstaller build script

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
Set-Location $Root

foreach ($path in @(
    (Join-Path $Root 'build'),
    (Join-Path $Root 'dist')
)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

$PyInstallerPath = (Get-Command pyinstaller -ErrorAction SilentlyContinue).Source
if (-not $PyInstallerPath) {
    Write-Error 'PyInstaller was not found. Run pip install pyinstaller and retry.'
}

$PythonRoot = Split-Path (Split-Path $PyInstallerPath -Parent) -Parent
$TclLibrary = Join-Path $PythonRoot 'tcl\tcl8.6'
$TkLibrary = Join-Path $PythonRoot 'tcl\tk8.6'

if (Test-Path $TclLibrary) {
    $env:TCL_LIBRARY = $TclLibrary
}
if (Test-Path $TkLibrary) {
    $env:TK_LIBRARY = $TkLibrary
}

$ExeName = -join @(
    [char]0x9867,
    [char]0x5ba2,
    [char]0x5225,
    [char]0x7d0d,
    [char]0x5165,
    [char]0x5206,
    [char]0x6790,
    [char]0x30b7,
    [char]0x30b9,
    [char]0x30c6,
    [char]0x30e0
)
$IconPng = Join-Path $Root 'docs\icon.png'
$IconIco = Join-Path $Root 'docs\icon.ico'
$PyInstallerArgs = @(
    '--noconfirm',
    '--windowed',
    '--onefile',
    '--name', $ExeName,
    '--specpath', (Join-Path $Root 'build\pyi_spec'),
    '--workpath', (Join-Path $Root 'build\pyi_work'),
    '--paths', $Root,
    '--additional-hooks-dir', (Join-Path $Root 'pyinstaller_hooks'),
    '--hidden-import', 'app.tk_app',
    '--hidden-import', '_tkinter',
    '--hidden-import', 'matplotlib.backends.backend_tkagg',
    '--hidden-import', 'tkinter',
    '--hidden-import', 'tkinter.ttk',
    '--hidden-import', 'tkinter.filedialog',
    '--hidden-import', 'tkinter.messagebox',
    '--exclude-module', 'PySide6',
    '--exclude-module', 'PyQt5',
    '--exclude-module', 'PyQt6',
    '--exclude-module', 'PySide2',
    '--exclude-module', 'scipy',
    '--exclude-module', 'sklearn',
    '--exclude-module', 'pytest',
    '--exclude-module', 'pyarrow',
    '--add-data', "$IconPng;docs",
    '--add-data', "$PythonRoot\tcl\tcl8.6;_tcl_data",
    '--add-data', "$PythonRoot\tcl\tk8.6;_tk_data",
    '--clean'
)

if (Test-Path $IconIco) {
    $PyInstallerArgs += @('--icon', $IconIco)
}

$PyInstallerArgs += "$Root\app\main.py"

pyinstaller @PyInstallerArgs
Write-Host ('Done (onefile): dist\{0}.exe only - no extra files required beside the .exe.' -f $ExeName)
