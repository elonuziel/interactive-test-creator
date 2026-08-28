#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH}"

if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    exec "$SCRIPT_DIR/.venv/bin/python" -m quizbuilder.gui "$@"
elif [ -f "$SCRIPT_DIR/../.venv/bin/python" ]; then
    exec "$SCRIPT_DIR/../.venv/bin/python" -m quizbuilder.gui "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 -m quizbuilder.gui "$@"
else
    exec python -m quizbuilder.gui "$@"
fi
