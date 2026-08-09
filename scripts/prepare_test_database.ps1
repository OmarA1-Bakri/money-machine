param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$LaneId
)

$ErrorActionPreference = "Stop"
$safeLane = ($LaneId.ToLowerInvariant() -replace '[^a-z0-9]+', '_').Trim('_')
if (-not $safeLane) { throw "lane id must contain a letter or digit" }

$database = "money_machine_test_$safeLane"
$user = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "money_machine" }
$password = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "local_development_only" }
$port = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "5432" }
$compose = Join-Path (Split-Path -Parent $PSScriptRoot) "compose.yaml"

docker compose -f $compose exec -T postgres psql -v ON_ERROR_STOP=1 -U $user -d postgres `
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$database' AND pid <> pg_backend_pid();" `
    -c "DROP DATABASE IF EXISTS `"$database`";" `
    -c "CREATE DATABASE `"$database`";" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "failed to prepare PostgreSQL test database" }

Write-Output "postgresql+asyncpg://${user}:${password}@127.0.0.1:${port}/${database}"
