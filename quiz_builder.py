#!/usr/bin/env python3
"""
quiz_builder.py — Root Entry Point for Interactive Hebrew Quiz Builder
Usage:
    python quiz_builder.py                # Run Batch CLI on tests/
    python quiz_builder.py [folder]       # Run Batch CLI on target folder
    python quiz_builder.py --gui          # Launch Desktop GUI Application
    python quiz_builder.py --build        # Build all ready quizzes into output/
    python quiz_builder.py --watch        # Live watch mode (auto-recompile on save)
    python quiz_builder.py --server       # Start local web server
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(SCRIPT_DIR, 'python_app')

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

if __name__ == '__main__':
    from quiz_builder_cli import main
    main()
