from __future__ import annotations

import importlib.util


REQUIRED_MODULES = {
    "fitz": "PyMuPDF",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
}


class DependencyError(RuntimeError):
    pass


def missing_dependencies() -> list[str]:
    return [package for module, package in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]


def require_dependencies() -> None:
    missing = missing_dependencies()
    if missing:
        names = " ".join(missing)
        raise DependencyError(
            f"Missing required Python packages: {', '.join(missing)}. "
            f"Install them with: python -m pip install {names}"
        )
