#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s RESEARCH_PACKET.json\n' "$0" >&2
  exit 64
fi

packet="$1"
python_bin="${PYTHON_BIN:-python}"

run_cli() {
  "$python_bin" -m money_machine.cli.main "$@"
}

run_cli db migrate --json
import_receipt="$(run_cli research import --packet "$packet" --json)"
printf '%s\n' "$import_receipt"
packet_id="$(printf '%s\n' "$import_receipt" | "$python_bin" -c \
  'import json,sys; print(json.load(sys.stdin)["packet_id"])')"

start_receipt="$(run_cli workflow start first-product --packet-id "$packet_id" --json)"
printf '%s\n' "$start_receipt"
workflow_id="$(printf '%s\n' "$start_receipt" | "$python_bin" -c \
  'import json,sys; print(json.load(sys.stdin)["workflow_run_id"])')"

run_cli worker drain --max-jobs 20 --json
status_receipt="$(run_cli workflow status "$workflow_id" --json)"
printf '%s\n' "$status_receipt"
state="$(printf '%s\n' "$status_receipt" | "$python_bin" -c \
  'import json,sys; print(json.load(sys.stdin)["state"])')"
if [[ "$state" != "DRAFT_READY" ]]; then
  printf 'workflow ended in %s\n' "$state" >&2
  exit 1
fi

run_cli artifacts inspect "$workflow_id" --json
