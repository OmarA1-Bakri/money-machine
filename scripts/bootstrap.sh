#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
command -v pnpm >/dev/null || { echo "pnpm is required" >&2; exit 1; }
command -v docker >/dev/null || { echo "Docker is required" >&2; exit 1; }

uv sync --frozen
pnpm install --frozen-lockfile
docker compose config --quiet
printf 'Bootstrap dependencies are ready. Run scripts/dev.sh to start the API.\n'
