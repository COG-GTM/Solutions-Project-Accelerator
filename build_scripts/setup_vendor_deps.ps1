# Fetch the vendored engine binaries that are deliberately NOT tracked in git.
#
# Run from the repo root (or anywhere - the script relocates itself), from the
# environment that already has requirements.txt installed:
#     powershell -ExecutionPolicy Bypass -File build_scripts/setup_vendor_deps.ps1
#
# Potrace, Poppler and anymd are downloaded from upstream and checked against the
# SHA-256 pinned in $Sources below. All three are programs invoked as separate
# processes, never linked, so they do not affect this project's own licence; see
# THIRD-PARTY-NOTICES.md (Potrace and Poppler are GPL-2.0 and carry a
# corresponding-source offer there; anymd is MIT).
# The PaddleOCR models are fetched by
# build_scripts/fetch_paddle_models.py, which resolves their URLs from the
# pip-installed `paddleocr` package rather than hardcoding a CDN address, and
# checksums the extracted files itself. The SAM2.1 segmentation models are
# downloaded from the mirrored Hugging Face repo below. Ollama is fetched as the
# official ollama-windows-amd64.zip release asset. Every hash was
# computed from the artifact that reproduces the engine tree this repo
# shipped at commit 1542e59.

param(
    [switch]$Force,
    # Interpreter that has requirements.txt installed. Defaults to the repo's
    # .venv when present, else whatever `python` resolves to. Pass an explicit
    # path to override.
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $Python) {
    $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
    $Python = if (Test-Path $venvPython) { $venvPython } else { 'python' }
}

# Capture stderr instead of discarding it: a bare `python` on Windows resolves to
# the Microsoft Store alias stub, and under $ErrorActionPreference='Stop' its
# stderr write is a terminating NativeCommandError that masks the message below.
# Assert on the interpreter's own output rather than $LASTEXITCODE, which a
# CommandNotFound leaves at its previous (possibly zero) value. The expected
# text must not appear literally in this source line: a PowerShell error record
# echoes the failing line, so a literal sentinel would match itself.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $probe = (& $Python -c "import sys; print('pyver=%d.%d' % sys.version_info[:2])" 2>&1 | Out-String)
} catch {
    $probe = ($_ | Out-String)
} finally {
    $ErrorActionPreference = $prevEap
}
if ($probe -notmatch 'pyver=3\.\d+') {
    throw ("'$Python' is not a usable Python 3 interpreter.`n" +
           "Activate the env with requirements.txt installed, or re-run with" +
           " -Python <path-to-python.exe>.`n" + $probe)
}

$Sources = [ordered]@{
    'Potrace' = @{
        Url    = 'https://potrace.sourceforge.net/download/1.16/potrace-1.16.win64.zip'
        Sha256 = '63699F9885B5ED053977FD94452A7BDBB77EE62B77BF28A3F17B2F14B9B9C65D'
    }
    'Poppler' = @{
        Url    = 'https://github.com/oschwartz10612/poppler-windows/releases/download/v26.09.0-0/Release-26.09.0-0.zip'
        Sha256 = '7A6F256A0DDF7536182246A5733331BF4677CBCC34F4663774947AD34556C8D0'
    }
    'AnyMD' = @{
        Url    = 'https://github.com/SylphxAI/anymd/releases/download/v8.5.1/anymd-win32-x64-msvc.zip'
        Sha256 = '84752AE8B2101CAECE34C3613A73B5AB06016F049A4A36EF0428339948349F75'
    }
    'SAM2.1-Encoder' = @{
        Url    = 'https://huggingface.co/mabote-itumeleng/ONNX-SAM2-Segment-Anything/resolve/main/sam2.1_hiera_tiny_encoder.onnx'
        Sha256 = '53C36ABB631CC60876F3EBE856A8D65B0A52F0CF8ECD24CCD8EE189E0F51E6CC'
    }
    'SAM2.1-Decoder' = @{
        Url    = 'https://huggingface.co/mabote-itumeleng/ONNX-SAM2-Segment-Anything/resolve/main/sam2.1_hiera_tiny_decoder.onnx'
        Sha256 = '4AF67A5D1108E5064FB8B12D3FF7FCBD1BB5B3EF931B6CBE31BBB851073812DA'
    }
    'Ollama' = @{
        Url    = 'https://github.com/ollama/ollama/releases/download/v0.34.3/ollama-windows-amd64.zip'
        Sha256 = '306CE9E81E3491D147F558E60D7A389499F244D10F71859C6E4E899241D1B4AE'
    }
}

# Sentinel file proving an engine is already installed.
$Sentinels = [ordered]@{
    'Potrace'           = 'Potrace\potrace-1.16.win64\potrace.exe'
    'Poppler'           = 'Poppler\poppler-26.09.0\Library\bin\pdftocairo.exe'
    'AnyMD'             = 'AnyMD\anymd.exe'
    'Paddle-OCR/cls'    = 'Paddle-OCR\cls\inference.pdiparams'
    'Paddle-OCR/det'    = 'Paddle-OCR\det\inference.pdiparams'
    'Paddle-OCR/rec'    = 'Paddle-OCR\rec\inference.pdiparams'
    'Paddle-OCR/layout' = 'Paddle-OCR\layout\inference.pdiparams'
    'Paddle-OCR/table'  = 'Paddle-OCR\table\inference.pdiparams'
    'SAM2.1/encoder'    = 'SAM2.1\sam2.1_hiera_tiny_encoder.onnx'
    'SAM2.1/decoder'    = 'SAM2.1\sam2.1_hiera_tiny_decoder.onnx'
    'Ollama'            = 'Ollama\ollama.exe'
}

$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("spa_vendor_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $stage | Out-Null

function Get-VerifiedArtifact {
    param([string]$Url, [string]$Sha256, [string]$Destination)

    Write-Host "    downloading $(Split-Path -Leaf $Url)"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -TimeoutSec 600

    $actual = (Get-FileHash $Destination -Algorithm SHA256).Hash
    if ($actual -ne $Sha256) {
        throw ("SHA-256 mismatch for $Url`n  expected $Sha256`n  actual   $actual`n" +
               "Refusing to install an artifact that does not match the pinned checksum.")
    }
    Write-Host "    checksum ok" -ForegroundColor DarkGray
}

function Install-PaddleModels {
    # URLs come from the pinned `paddleocr` package installed by pip, so the
    # repo never carries a model CDN address of its own.
    $pyArgs = @((Join-Path $PSScriptRoot 'fetch_paddle_models.py'))
    if ($Force) { $pyArgs += '--force' }
    & $Python @pyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "fetch_paddle_models.py failed (exit $LASTEXITCODE). Install requirements.txt first."
    }
}

function Install-Potrace {
    $zip = Join-Path $stage 'potrace.zip'
    Get-VerifiedArtifact -Url $Sources['Potrace'].Url -Sha256 $Sources['Potrace'].Sha256 -Destination $zip

    $target = Join-Path $repoRoot 'Potrace'
    Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
    # The zip already contains the potrace-1.16.win64\ folder the app path expects.
    Expand-Archive -Path $zip -DestinationPath $target -Force
}

function Install-Poppler {
    $zip = Join-Path $stage 'poppler.zip'
    Get-VerifiedArtifact -Url $Sources['Poppler'].Url -Sha256 $Sources['Poppler'].Sha256 -Destination $zip

    $target = Join-Path $repoRoot 'Poppler'
    Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
    # The zip already contains the poppler-26.09.0\ folder the app path expects.
    Expand-Archive -Path $zip -DestinationPath $target -Force
}

function Install-AnyMD {
    $zip = Join-Path $stage 'anymd.zip'
    Get-VerifiedArtifact -Url $Sources['AnyMD'].Url -Sha256 $Sources['AnyMD'].Sha256 -Destination $zip

    $target = Join-Path $repoRoot 'AnyMD'
    Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
    # The zip is a bare anymd.exe, so it extracts straight into AnyMD\.
    Expand-Archive -Path $zip -DestinationPath $target -Force
}

function Install-SAM2Models {
    $target = Join-Path $repoRoot 'SAM2.1'
    New-Item -ItemType Directory -Force -Path $target | Out-Null

    $encoder = Join-Path $target 'sam2.1_hiera_tiny_encoder.onnx'
    Get-VerifiedArtifact -Url $Sources['SAM2.1-Encoder'].Url -Sha256 $Sources['SAM2.1-Encoder'].Sha256 -Destination $encoder

    $decoder = Join-Path $target 'sam2.1_hiera_tiny_decoder.onnx'
    Get-VerifiedArtifact -Url $Sources['SAM2.1-Decoder'].Url -Sha256 $Sources['SAM2.1-Decoder'].Sha256 -Destination $decoder
}

function Install-Ollama {
    $zip = Join-Path $stage 'ollama-windows-amd64.zip'
    Get-VerifiedArtifact -Url $Sources['Ollama'].Url -Sha256 $Sources['Ollama'].Sha256 -Destination $zip

    $target = Join-Path $repoRoot 'Ollama'
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    # Only overlays ollama.exe + lib\ollama; leaves any pulled models\ alone.
    Expand-Archive -Path $zip -DestinationPath $target -Force
}

try {
    if ((Test-Path (Join-Path $repoRoot $Sentinels['Potrace'])) -and -not $Force) {
        Write-Host "[skip]    Potrace already present" -ForegroundColor DarkGray
    }
    else {
        Write-Host "[install] Potrace" -ForegroundColor Cyan
        Install-Potrace
    }

    if ((Test-Path (Join-Path $repoRoot $Sentinels['Poppler'])) -and -not $Force) {
        Write-Host "[skip]    Poppler already present" -ForegroundColor DarkGray
    }
    else {
        Write-Host "[install] Poppler (pdftocairo)" -ForegroundColor Cyan
        Install-Poppler
    }

    if ((Test-Path (Join-Path $repoRoot $Sentinels['AnyMD'])) -and -not $Force) {
        Write-Host "[skip]    anymd already present" -ForegroundColor DarkGray
    }
    else {
        Write-Host "[install] anymd (PDF to Markdown)" -ForegroundColor Cyan
        Install-AnyMD
    }

    Install-PaddleModels

    if ((Test-Path (Join-Path $repoRoot $Sentinels['SAM2.1/encoder'])) -and
        (Test-Path (Join-Path $repoRoot $Sentinels['SAM2.1/decoder'])) -and -not $Force) {
        Write-Host "[skip]    SAM2.1 models already present" -ForegroundColor DarkGray
    }
    else {
        Write-Host "[install] SAM2.1 segmentation models" -ForegroundColor Cyan
        Install-SAM2Models
    }

    if ((Test-Path (Join-Path $repoRoot $Sentinels['Ollama'])) -and -not $Force) {
        Write-Host "[skip]    Ollama already present" -ForegroundColor DarkGray
    }
    else {
        Write-Host "[install] Ollama" -ForegroundColor Cyan
        Install-Ollama
    }
}
finally {
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}

$missing = $Sentinels.Values | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
if ($missing) {
    throw ("Setup finished but these files are still missing:`n  " + ($missing -join "`n  "))
}
Write-Host "All vendored engines are in place." -ForegroundColor Green
