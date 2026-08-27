from __future__ import annotations

from pathlib import Path
import sys


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def tests_root() -> Path:
    return application_root() / "tests"


def scripts_root() -> Path:
    return application_root() / "python_scripts"


def web_root() -> Path:
    return application_root() / "web"

