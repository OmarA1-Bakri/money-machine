#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Docker Desktop can configure its Windows credential helper without adding the
# helper directory to a WSL shell's PATH. Keep this repair process-local.
docker_desktop_bin="/mnt/c/Program Files/Docker/Docker/resources/bin"
if ! command -v docker-credential-desktop.exe >/dev/null 2>&1 && [[ -d "$docker_desktop_bin" ]]; then
  export PATH="$docker_desktop_bin:$PATH"
fi

command -v docker >/dev/null || { echo "Docker is required" >&2; exit 1; }

docker compose up --detach --wait postgres

result="$({ docker compose exec -T postgres sh -ec \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec psql --host=127.0.0.1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --no-password --set=ON_ERROR_STOP=1 --tuples-only --no-align --command="SELECT 1;"'; } 2>&1)" || {
  printf 'Authenticated PostgreSQL TCP connection failed:\n%s\n' "$result" >&2
  exit 1
}

if [[ "${result//$'\r'/}" != "1" ]]; then
  printf 'PostgreSQL smoke query returned an unexpected result: %q\n' "$result" >&2
  exit 1
fi

printf 'Authenticated PostgreSQL TCP connection succeeded.\n'
