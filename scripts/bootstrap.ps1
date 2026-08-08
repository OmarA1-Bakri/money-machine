$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required" }
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw "pnpm is required" }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is required" }

uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
pnpm install --frozen-lockfile
if ($LASTEXITCODE -ne 0) { throw "pnpm install failed" }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed" }
Write-Host "Bootstrap dependencies are ready. Run scripts/dev.ps1 to start the API."
