$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Commands = @(
    @("sync", "--frozen"),
    @("run", "--frozen", "ruff", "format", "--check", "src", "tests", "scripts"),
    @("run", "--frozen", "ruff", "check", "src", "tests", "scripts", "apps"),
    @("run", "--frozen", "pyright"),
    @("run", "--frozen", "pytest")
)

foreach ($Arguments in $Commands) {
    & uv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: uv $Arguments" }
}

docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed" }
