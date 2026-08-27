from __future__ import annotations

from pathlib import Path
import sys


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def tests_root() -> Path:
    bundled_tests = application_root() / "tests"
    if bundled_tests.is_dir():
        return bundled_tests
    repository_tests = application_root().parent / "tests"
    if repository_tests.is_dir():
        return repository_tests
    return bundled_tests


def scripts_root() -> Path:
    return application_root() / "python_scripts"


def web_root() -> Path:
    return application_root() / "web"

