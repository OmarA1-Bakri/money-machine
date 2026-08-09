#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s LANE_ID\n' "$0" >&2
  exit 64
fi

lane_id="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+|_+$//g')"
if [[ -z "$lane_id" ]]; then
  printf 'lane id must contain a letter or digit\n' >&2
  exit 64
fi

db="money_machine_test_${lane_id}"
user="${POSTGRES_USER:-money_machine}"
password="${POSTGRES_PASSWORD:-local_development_only}"
port="${POSTGRES_PORT:-5432}"
compose_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/compose.yaml"

docker compose -f "$compose_file" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$user" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS \"$db\";" \
  -c "CREATE DATABASE \"$db\";" >/dev/null

printf 'postgresql+asyncpg://%s:%s@127.0.0.1:%s/%s\n' "$user" "$password" "$port" "$db"
