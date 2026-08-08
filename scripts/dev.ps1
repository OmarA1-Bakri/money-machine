$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { "8000" }

uv run --frozen uvicorn money_machine.api.main:app --host 127.0.0.1 --port $ApiPort --reload
exit $LASTEXITCODE

