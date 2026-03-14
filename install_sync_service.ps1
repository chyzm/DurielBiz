$ErrorActionPreference = "Stop"

param(
  [string]$Username,
  [string]$Password
)

$serviceExePath = Join-Path $PSScriptRoot "dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe"
if (-not (Test-Path $serviceExePath)) {
  throw "Sync service executable not found at $serviceExePath. Build it first with .\build_desktop.ps1."
}

if ($Username -and $Password) {
  & $serviceExePath "--username" $Username "--password" $Password "--startup" "auto" "install"
} else {
  & $serviceExePath "--startup" "auto" "install"
}
& $serviceExePath "start"
