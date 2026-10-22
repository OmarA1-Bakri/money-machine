#!/usr/bin/env bash
# Isolated official Graphify tool; no app dependencies, model backend or source upload.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tools_root="${MONEY_MACHINE_TOOLS_ROOT:-$(dirname "$repo_root")/.tools}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$(dirname "$repo_root")/.cache/uv}"
export UV_TOOL_DIR="$tools_root/uv"
export UV_TOOL_BIN_DIR="$tools_root/bin"
uv tool install graphifyy==0.9.93 "$@"
uv tool list
printf 'Graphify executable: %s\n' "$UV_TOOL_BIN_DIR/graphify"
# Review installed help and source before selecting code-only extraction or
# project skill registration. Installing a tool alone does not prove a graph.
