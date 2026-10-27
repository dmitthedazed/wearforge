# WearForge installer for Windows.
#   irm https://raw.githubusercontent.com/dmitthedazed/wearforge/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$Repo = "dmitthedazed/wearforge"
$Ref = if ($env:WEARFORGE_REF) { $env:WEARFORGE_REF } else { "main" }
$Src = "https://github.com/$Repo/archive/refs/heads/$Ref.zip"
$AppDir = Join-Path $env:LOCALAPPDATA "WearForge-app"
$BinDir = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"

function Say($msg) { Write-Host ":: " -ForegroundColor Cyan -NoNewline; Write-Host $msg }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

# --- dependencies: python + adb ---
$py = Get-Command python -ErrorAction SilentlyContinue |
      Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1
if (-not $py) {
    if (-not (Have winget)) { throw "Install Python 3.9+ from https://python.org and rerun." }
    Say "installing python"
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Refresh-Path
    $py = Get-Command python -ErrorAction Stop
}
if (-not (Have adb)) {
    if (-not (Have winget)) { throw "Install Android platform-tools (adb) and rerun." }
    Say "installing android platform-tools"
    winget install -e --id Google.PlatformTools --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Refresh-Path
}

# --- app: isolated venv + launcher on PATH ---
Say "installing wearforge"
& $py.Source -m venv (Join-Path $AppDir "venv")
$venvPy = Join-Path $AppDir "venv\Scripts\python.exe"
& $venvPy -m pip install -q --upgrade pip
& $venvPy -m pip install -q --upgrade $Src
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$exe = Join-Path $AppDir "venv\Scripts\wearforge.exe"
Set-Content -Path (Join-Path $BinDir "wearforge.cmd") -Value "@`"$exe`" %*" -Encoding ASCII

Say "done. open a new terminal and run: wearforge"
