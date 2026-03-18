#!/usr/bin/env bash
# Validator wrapper pour recipe-book.
# Usage: ./validators/recipe-book.sh <workdir> <port>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKDIR="${1:?workdir required}"
PORT="${2:-8000}"

exec python3 "$SCRIPT_DIR/recipe-book.py" "$WORKDIR" "$PORT"
