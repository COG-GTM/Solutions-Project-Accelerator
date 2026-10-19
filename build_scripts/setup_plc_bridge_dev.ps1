# One-shot dev setup for the Rockwell PLC sidecar.
#
# Creates the build virtualenv, installs numpy + pyinstaller + the two
# Rockwell SDK wheels, builds rockwell_plc_bridge.exe, and smoke-tests
# it with `--version`. Idempotent: rerun to refresh wheels; use -Force
# to blow the env away and start from scratch.
#
# Run from the repo root or anywhere else; the script cd's to the
# repo automatically.
#
#     powershell -ExecutionPolicy Bypass -File build_scripts/setup_plc_bridge_dev.ps1
#     powershell -ExecutionPolicy Bypass -File build_scripts/setup_plc_bridge_dev.ps1 -Force
#     powershell -ExecutionPolicy Bypass -File build_scripts/setup_plc_bridge_dev.ps1 -SkipBuild

param(
    [string]$VenvPath = 'plc_bridge\.venv',
    [string]$Python = '',   # base interpreter used to create the venv; auto-probed when empty
    [string]$LogixDesignerWheelDir = 'C:\Users\Public\Documents\Studio 5000\Logix Designer SDK\python',
    [string]$LogixEchoWheelDir = 'C:\Users\Public\Documents\FactoryTalk Logix Echo\SDK\Python',
    [switch]$Force,         # delete any existing venv at that path first
    [switch]$SkipBuild,     # provision env only; skip pyinstaller
    [switch]$SkipSmokeTest  # skip the final --version check on the exe
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Fail($msg) {
    Write-Host $msg -ForegroundColor Red
    exit 1
}

# --- 0. Preflight ----------------------------------------------------
Write-Step "Preflight"

# Bare `python` on Windows is often the Microsoft Store alias stub, which prints
# "Python was not found" to stderr and exits 9009. Probe candidates until one
# actually reports a version. stderr is captured rather than redirected to $null:
# under $ErrorActionPreference='Stop' an uncaptured native stderr write is terminating.
function Resolve-BasePython([string]$explicit) {
    $candidates = if ($explicit) { @($explicit) } else { @('py -3.12', 'py -3', 'python') }
    foreach ($candidate in $candidates) {
        $parts = $candidate -split ' '
        $cmd = $parts[0]
        # $parts[1..0] would reverse-enumerate on a single-word candidate, so guard the slice.
        $cmdArgs = @()
        if ($parts.Length -gt 1) { $cmdArgs = $parts[1..($parts.Length - 1)] }
        if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }

        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $out = (& $cmd @cmdArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1 | Out-String)
        } catch {
            $out = ''
        } finally {
            $ErrorActionPreference = $prev
        }

        if ($LASTEXITCODE -eq 0 -and $out -match '(?m)^\s*3\.(\d+)\s*$') {
            return [pscustomobject]@{ Cmd = $cmd; Args = $cmdArgs; Version = $Matches[0].Trim() }
        }
    }
    Fail @"
No working Python 3.12 interpreter found (tried: $($candidates -join ', ')).
If 'python' opened the Microsoft Store, that is the App Execution Alias stub, not
a real interpreter: turn it off under Settings > Apps > Advanced app settings >
App execution aliases.
Install Python 3.12 from https://www.python.org/downloads/ (tick "Add python.exe
to PATH"), or point this script at one explicitly:
    -Python 'C:\path\to\python.exe'
"@
}

$basePython = Resolve-BasePython $Python
Write-Host "base python: $($basePython.Cmd) $($basePython.Args -join ' ') (3.x = $($basePython.Version))"
if ($basePython.Version -ne '3.12') {
    Write-Host "WARNING: expected Python 3.12, got $($basePython.Version). The Rockwell SDK wheels are cp312." -ForegroundColor Yellow
}

$specPath = Join-Path $repoRoot 'plc_bridge/rockwell_plc_bridge.spec'
if (-not (Test-Path $specPath)) {
    Fail "Sidecar PyInstaller spec not found at $specPath. Is this the right repo?"
}

# --- 1. Locate wheels ------------------------------------------------
Write-Step "Locating Rockwell SDK wheels"

function Get-LatestWheel($dir, $prefix, $installerName) {
    if (-not (Test-Path $dir)) {
        Fail @"
Expected $installerName wheel directory does not exist:
    $dir
Install "$installerName" from Rockwell (it drops the wheel there), or
rerun with an override, e.g.:
    -LogixDesignerWheelDir 'D:\path\to\wheels'
"@
    }
    $wheel = Get-ChildItem -Path $dir -Filter "$prefix-*.whl" -File `
             | Sort-Object Name -Descending `
             | Select-Object -First 1
    if (-not $wheel) {
        Fail @"
No $prefix-*.whl wheel found in:
    $dir
Reinstall "$installerName" from Rockwell to restore the wheel, or point
this script at another directory with an override flag.
"@
    }
    return $wheel.FullName
}

$designerWheel = Get-LatestWheel `
    -dir $LogixDesignerWheelDir `
    -prefix 'logix_designer_sdk' `
    -installerName 'Studio 5000 Logix Designer SDK'
Write-Host "Logix Designer wheel: $designerWheel" -ForegroundColor Green

$echoWheel = Get-LatestWheel `
    -dir $LogixEchoWheelDir `
    -prefix 'ftecho_sdk' `
    -installerName 'FactoryTalk Logix Echo SDK'
Write-Host "Logix Echo wheel:     $echoWheel" -ForegroundColor Green

# --- 2. (Re)create the virtualenv ------------------------------------
$venvRoot = if ([System.IO.Path]::IsPathRooted($VenvPath)) { $VenvPath }
            else { Join-Path $repoRoot $VenvPath }
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
$venvPyinstaller = Join-Path $venvRoot 'Scripts\pyinstaller.exe'

Write-Step "Provisioning virtualenv '$VenvPath'"

if ((Test-Path $venvRoot) -and $Force) {
    Write-Host "Removing existing venv '$VenvPath' (-Force)..."
    Remove-Item -LiteralPath $venvRoot -Recurse -Force
}

if (-not (Test-Path $venvPython)) {
    & $basePython.Cmd @($basePython.Args) -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { Fail "venv creation failed (exit $LASTEXITCODE)." }
} else {
    Write-Host "Venv '$VenvPath' already exists; refreshing packages (use -Force to rebuild from scratch)."
}
if (-not (Test-Path $venvPython)) { Fail "venv created but $venvPython is missing." }

# --- 3. Install runtime + build deps ---------------------------------
Write-Step "Installing numpy + pyinstaller + SDK wheels into '$VenvPath'"

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "pip self-upgrade failed (exit $LASTEXITCODE)." }

& $venvPython -m pip install --upgrade numpy pyinstaller
if ($LASTEXITCODE -ne 0) { Fail "pip install numpy/pyinstaller failed (exit $LASTEXITCODE)." }

& $venvPython -m pip install --upgrade "$designerWheel"
if ($LASTEXITCODE -ne 0) { Fail "pip install of Logix Designer wheel failed (exit $LASTEXITCODE)." }

& $venvPython -m pip install --upgrade "$echoWheel"
if ($LASTEXITCODE -ne 0) { Fail "pip install of Logix Echo wheel failed (exit $LASTEXITCODE)." }

# Verify both SDKs are importable inside the env before we spend time
# on the PyInstaller build.
Write-Step "Verifying SDK imports in '$VenvPath'"
& $venvPython -c @"
import importlib, importlib.metadata as m
for name in ('logix_designer_sdk', 'ftecho_sdk'):
    importlib.import_module(name)
    print(f'{name} {m.version(name)} OK')
"@
if ($LASTEXITCODE -ne 0) {
    Fail "SDK import verification failed. Inspect the pip output above."
}

if ($SkipBuild) {
    Write-Host ""
    Write-Host "Venv '$VenvPath' is ready. -SkipBuild set; not running pyinstaller." -ForegroundColor Yellow
    Write-Host "Next: build_scripts/build_all.ps1 (two-stage) or manually run:" -ForegroundColor Yellow
    Write-Host "    $venvPyinstaller plc_bridge/rockwell_plc_bridge.spec --distpath plc_bridge/dist" -ForegroundColor Yellow
    exit 0
}

# --- 4. Build the sidecar --------------------------------------------
Write-Step "Building rockwell_plc_bridge.exe with PyInstaller"

& $venvPyinstaller `
    plc_bridge/rockwell_plc_bridge.spec `
    --distpath plc_bridge/dist `
    --workpath plc_bridge/build `
    --noconfirm
if ($LASTEXITCODE -ne 0) {
    Fail "PyInstaller build failed (exit $LASTEXITCODE)."
}

$sidecarExe = Join-Path $repoRoot 'plc_bridge/dist/rockwell_plc_bridge/rockwell_plc_bridge.exe'
if (-not (Test-Path $sidecarExe)) {
    Fail "PyInstaller reported success but the exe was not produced at: $sidecarExe"
}
Write-Host "Sidecar built: $sidecarExe" -ForegroundColor Green

# --- 5. Smoke test ---------------------------------------------------
if ($SkipSmokeTest) {
    Write-Host ""
    Write-Host "Skipping --version smoke test (-SkipSmokeTest set)." -ForegroundColor Yellow
    exit 0
}

Write-Step "Smoke-testing sidecar (--version)"

# The exe is standalone, so it runs directly off the filesystem. Capture
# stdout and confirm the JSON handshake matches expectations.
$versionOutput = & $sidecarExe --version
if ($LASTEXITCODE -ne 0) {
    Fail "Sidecar --version exited $LASTEXITCODE. Output:`n$versionOutput"
}

Write-Host $versionOutput
try {
    $parsed = $versionOutput | ConvertFrom-Json
} catch {
    Fail "Sidecar --version did not emit valid JSON. Output above."
}
if ($parsed.event -ne 'result' -or $parsed.ok -ne $true -or -not $parsed.data.version) {
    Fail "Sidecar --version emitted unexpected JSON shape. Output above."
}
if (-not $parsed.data.logix_designer_sdk) {
    Write-Host "WARNING: sidecar reports logix_designer_sdk as null. Did the wheel install cleanly?" -ForegroundColor Yellow
}
if (-not $parsed.data.ftecho_sdk) {
    Write-Host "WARNING: sidecar reports ftecho_sdk as null. Did the wheel install cleanly?" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Dev setup complete." -ForegroundColor Green
Write-Host "    sidecar version: $($parsed.data.version)"
Write-Host "    logix_designer_sdk: $($parsed.data.logix_designer_sdk)"
Write-Host "    ftecho_sdk:         $($parsed.data.ftecho_sdk)"
Write-Host ""
Write-Host "Run the main app (from the main .venv) and Tools > Build PLC menus" -ForegroundColor Green
Write-Host "will now find the sidecar under plc_bridge/dist/rockwell_plc_bridge/." -ForegroundColor Green
