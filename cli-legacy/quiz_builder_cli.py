#!/usr/bin/env python3
"""Compatibility launcher for the refactored quizbuilder package."""

from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent / "src"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from quizbuilder.cli import main
from quizbuilder.config import Config
from quizbuilder.documents import (
    classify_pdf,
    convert_docx_batch,
    convert_docx_to_pdf_with_soffice,
    convert_docx_with_soffice,
    detect_docx_converter,
    find_soffice,
)
from quizbuilder.models import Workspace
from quizbuilder.providers import detect_freebuff_command
from quizbuilder.wizard import run_workspace


def process_workspace(test_name: str, test_dir: str) -> None:
    config = Config.load()
    workspace = Workspace(test_name, Path(test_dir))
    run_workspace(config, workspace)


if __name__ == "__main__":
    raise SystemExit(main())
