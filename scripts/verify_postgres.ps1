$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is required" }

docker compose up --detach --wait postgres
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL failed to start and become healthy" }

$Result = docker compose exec -T postgres sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" exec psql --host=127.0.0.1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --no-password --set=ON_ERROR_STOP=1 --tuples-only --no-align --command="SELECT 1;"'
if ($LASTEXITCODE -ne 0) { throw "Authenticated PostgreSQL TCP connection failed" }
if (($Result | Out-String).Trim() -ne "1") {
    throw "PostgreSQL smoke query returned an unexpected result: $Result"
}

Write-Host "Authenticated PostgreSQL TCP connection succeeded."
