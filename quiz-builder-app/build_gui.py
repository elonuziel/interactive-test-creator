#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


BASE_DIR = Path(__file__).resolve().parent
SPEC_FILE = BASE_DIR / "quiz_builder_gui.spec"
DIST_DIR = BASE_DIR / "dist"
WORK_DIR = BASE_DIR / "build"


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={WORK_DIR}",
        str(SPEC_FILE),
    ]
    result = subprocess.run(command, cwd=BASE_DIR)
    if result.returncode == 0:
        print(f"GUI build completed in {DIST_DIR / 'quiz_builder_gui'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
