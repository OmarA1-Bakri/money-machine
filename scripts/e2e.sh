#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" == 1 && "$1" == "--fixture" ]]; then
  exec "${MONEY_MACHINE_PYTHON:-.venv/bin/python}" -m money_machine.cli.fixture
fi
printf '%s\n' 'e2e is uncommissioned; no external or durable action was performed.' >&2
exit 78
