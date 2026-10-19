# Two-stage PyInstaller build.
#
# Stage 0: verify the vendored engines are present (they are not in git;
# fetch them with build_scripts/setup_vendor_deps.ps1).
# Stage 1: rockwell_plc_bridge.exe sidecar (numpy-2 venv). Requires the
# Rockwell Logix Designer SDK and Logix Echo SDK wheels installed in
# $SidecarVenv. Pass -SkipPlcBridge to omit this stage entirely (e.g. on a
# machine without those SDKs) - runme.spec bundles the sidecar only if its
# COLLECT dir exists, so Stage 2 still produces a working runme.exe, just
# without Tools > Build PLC support.
# Stage 2: main runme.exe (numpy-1 venv). Stage 1's COLLECT dir is
# picked up automatically by runme.spec and bundled under
# _internal/rockwell_plc_bridge/.
#
# Run from the repo root:
#     powershell -ExecutionPolicy Bypass -File build_scripts/build_all.ps1
#     powershell -ExecutionPolicy Bypass -File build_scripts/build_all.ps1 -SkipPlcBridge

param(
    [string]$SidecarVenv = 'plc_bridge\.venv',
    [string]$MainVenv    = '.venv',
    [switch]$SkipPlcBridge
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Resolve-VenvTool([string]$venvPath, [string]$tool) {
    $root = if ([System.IO.Path]::IsPathRooted($venvPath)) { $venvPath }
            else { Join-Path $repoRoot $venvPath }
    $exe = Join-Path $root "Scripts\$tool.exe"
    if (-not (Test-Path $exe)) {
        throw ("'$tool' not found in virtualenv '$venvPath' (looked for $exe).`n" +
               "Create the environment first - see README.md 'Quick start', or for the" +
               " sidecar:`n  powershell -ExecutionPolicy Bypass -File build_scripts/setup_plc_bridge_dev.ps1")
    }
    return $exe
}

# runme.spec bundles these wholesale; without them the build silently ships an app with no OCR.
Write-Host "=== Stage 0: check vendored engines ===" -ForegroundColor Cyan
$requiredEngineFiles = @(
    'Potrace\potrace-1.16.win64\potrace.exe'
    'Poppler\poppler-26.09.0\Library\bin\pdftocairo.exe'
    'AnyMD\anymd.exe'
    'Paddle-OCR\det\inference.pdmodel'
    'SAM2.1\sam2.1_hiera_tiny_encoder.onnx'
    'SAM2.1\sam2.1_hiera_tiny_decoder.onnx'
)
$missingEngineFiles = $requiredEngineFiles | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
if ($missingEngineFiles) {
    throw ("Vendored engines are missing:`n  " + ($missingEngineFiles -join "`n  ") +
           "`nFetch them first:`n" +
           "  powershell -ExecutionPolicy Bypass -File build_scripts/setup_vendor_deps.ps1")
}
Write-Host "Vendored engines present." -ForegroundColor Green

if ($SkipPlcBridge) {
    Write-Host "=== Stage 1: skipped (-SkipPlcBridge) - no Logix Designer/Echo SDK required ===" -ForegroundColor Yellow
    Write-Host "runme.exe will build without the PLC bridge sidecar; Tools > Build PLC will show an install hint." -ForegroundColor Yellow
} else {
    Write-Host "=== Stage 1: build rockwell_plc_bridge sidecar in '$SidecarVenv' ===" -ForegroundColor Cyan
    & (Resolve-VenvTool $SidecarVenv 'pyinstaller') `
        plc_bridge/rockwell_plc_bridge.spec `
        --distpath plc_bridge/dist `
        --workpath plc_bridge/build `
        --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "Sidecar build failed (exit $LASTEXITCODE)."
    }

    $sidecarExe = Join-Path $repoRoot 'plc_bridge/dist/rockwell_plc_bridge/rockwell_plc_bridge.exe'
    if (-not (Test-Path $sidecarExe)) {
        throw "Sidecar exe not found at expected path: $sidecarExe"
    }
    Write-Host "Sidecar built: $sidecarExe" -ForegroundColor Green
}

Write-Host "=== Stage 2: build main runme in '$MainVenv' ===" -ForegroundColor Cyan
$mainPython = Resolve-VenvTool $MainVenv 'python'
# PyInstaller's paddle/paddleocr hooks import pkg_resources at build time; setuptools
# >= 81 dropped it, which crashes here with a cryptic ModuleNotFoundError.
# Capture stderr into a variable: setuptools 80.x prints a deprecation warning there,
# and under $ErrorActionPreference='Stop' an uncaptured native stderr write aborts the script.
$pkgResourcesProbe = & $mainPython -W ignore -c "import pkg_resources" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw ("'$MainVenv' is missing pkg_resources (setuptools >= 81 removed it).`n" +
           "Fix with: $mainPython -m pip install `"setuptools<81`"`n" +
           ($pkgResourcesProbe | Out-String))
}
& (Resolve-VenvTool $MainVenv 'pyinstaller') runme.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "Main runme build failed (exit $LASTEXITCODE)."
}

$mainExe = Join-Path $repoRoot 'dist/runme/runme.exe'
if (Test-Path $mainExe) {
    Write-Host "Main app built: $mainExe" -ForegroundColor Green
} else {
    Write-Host "Main app build finished but runme.exe was not found at $mainExe" -ForegroundColor Yellow
}
