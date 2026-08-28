#!/usr/bin/env bash
set -e

# Interactive Hebrew Quiz Builder - Linux Launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python runtime (virtual environment preferred, then PATH)
PYTHON_BIN=""
if [ -f "$SCRIPT_DIR/quiz-builder-app/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/quiz-builder-app/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python runtime not found. Please install Python 3.11+ or create a virtual environment."
    exit 1
fi

export PYTHONPATH="$SCRIPT_DIR/quiz-builder-app/src:${PYTHONPATH}"
exec "$PYTHON_BIN" -m quizbuilder.gui "$@"

