param(
  [switch]$Backend,
  [switch]$Frontend
)

# default: start both
if (-not $Backend -and -not $Frontend) {
  $Backend = $true
  $Frontend = $true
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

if ($Backend) {
  $backendDir = Join-Path $projectRoot "backend"
  Write-Host "Starting backend in new PowerShell process (cwd: $backendDir)"
  Start-Process -FilePath pwsh -ArgumentList "-NoProfile","-NoExit","-Command","uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000" -WorkingDirectory $backendDir
}

if ($Frontend) {
  $frontendDir = Join-Path $projectRoot "frontend"
  Write-Host "Starting frontend in new PowerShell process (cwd: $frontendDir)"
  Start-Process -FilePath pwsh -ArgumentList "-NoProfile","-NoExit","-Command","pnpm run dev" -WorkingDirectory $frontendDir
}
