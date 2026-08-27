#!/usr/bin/env bash
# Launch the Interactive Hebrew Quiz Builder desktop GUI
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH="$SCRIPT_DIR/src" python -m quizbuilder.gui "$@"
