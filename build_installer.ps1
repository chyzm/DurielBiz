$ErrorActionPreference = "Stop"

$exePath = Join-Path $PSScriptRoot "dist\DurielBizPOS.exe"
if (-not (Test-Path $exePath)) {
  throw "Desktop executable not found at $exePath. Build it first with .\build_desktop.ps1."
}

$adminExePath = Join-Path $PSScriptRoot "dist\DurielBizPOSAdmin.exe"
if (-not (Test-Path $adminExePath)) {
  throw "Desktop admin executable not found at $adminExePath. Build it first with .\build_desktop.ps1."
}

$serviceExePath = Join-Path $PSScriptRoot "dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe"
if (-not (Test-Path $serviceExePath)) {
  throw "Desktop sync service executable not found at $serviceExePath. Build it first with .\build_desktop.ps1."
}

$compilerCandidates = @(
  $env:INNO_SETUP_COMPILER,
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
  "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ }

$compiler = $compilerCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $compiler) {
  throw "Inno Setup compiler not found. Install Inno Setup 6 or set INNO_SETUP_COMPILER to ISCC.exe."
}

& $compiler (Join-Path $PSScriptRoot "DurielBizPOS.iss")
