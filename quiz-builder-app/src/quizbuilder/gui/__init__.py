"""Interactive quiz builder GUI package.

PySide6 is imported lazily (PEP 562 module ``__getattr__``) so that
``import quizbuilder.gui`` keeps working — and ``quizbuilder.gui.main()``
raises a helpful ``RuntimeError`` — in environments without Qt installed.
"""

from __future__ import annotations

import sys

__all__ = ["main", "QuizBuilderWindow", "LITE_STYLESHEET"]


def main() -> int:
    if sys.modules.get("PySide6.QtWidgets") is None and "PySide6" in sys.modules:
        raise RuntimeError(
            "The GUI requires PySide6. Install it with: python -m pip install PySide6"
        )
    try:
        from .app import main as run
    except ImportError as exc:
        raise RuntimeError(
            "The GUI requires PySide6. Install it with: python -m pip install PySide6"
        ) from exc
    return run()


def __getattr__(name: str):
    if name == "main":
        return main
    if name == "QuizBuilderWindow":
        from .app import QuizBuilderWindow

        return QuizBuilderWindow
    if name == "LITE_STYLESHEET":
        from .styles import LITE_STYLESHEET

        return LITE_STYLESHEET
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
