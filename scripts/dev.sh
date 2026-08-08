#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

exec uv run --frozen uvicorn money_machine.api.main:app --host 127.0.0.1 --port "${API_PORT:-8000}" --reload

