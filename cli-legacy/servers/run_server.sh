#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    printf '%s\n' 'Error: Python 3 is required but was not found on PATH.' >&2
    exit 1
fi

exec "$PYTHON_BIN" -m quizbuilder serve --port "${PORT:-8000}"
