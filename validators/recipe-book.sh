#!/usr/bin/env bash
# Validator wrapper pour recipe-book.
# Usage: ./validators/recipe-book.sh <workdir> <port> [venv_dir]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKDIR="${1:?workdir required}"
PORT="${2:-8000}"
VENV_DIR="${3:-}"

# Choisir l'interpréteur Python
if [[ -n "$VENV_DIR" && -f "$VENV_DIR/bin/python" ]]; then
  PYTHON="$VENV_DIR/bin/python"
  # Installer playwright dans le venv si absent
  if ! "$PYTHON" -c "import playwright" 2>/dev/null; then
    echo "Installation de playwright dans le venv..."
    uv pip install --python "$PYTHON" playwright --quiet
    "$VENV_DIR/bin/playwright" install chromium --quiet 2>/dev/null || \
      "$PYTHON" -m playwright install chromium 2>/dev/null
  fi
else
  PYTHON="python3"
fi

exec "$PYTHON" "$SCRIPT_DIR/recipe-book.py" "$WORKDIR" "$PORT" "$PYTHON"
