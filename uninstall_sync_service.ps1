$ErrorActionPreference = "Stop"

$serviceExePath = Join-Path $PSScriptRoot "dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe"
if (-not (Test-Path $serviceExePath)) {
  throw "Sync service executable not found at $serviceExePath."
}

try {
  & $serviceExePath "stop"
} catch {
}

& $serviceExePath "remove"
