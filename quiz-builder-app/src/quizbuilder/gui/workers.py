"""Background task helpers for the quiz builder GUI."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    """Run a callable on a QThreadPool and emit its result or error text."""

    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.finished.emit(self.function())
        except Exception as exc:
            logging.getLogger(__name__).exception("Background GUI task failed")
            self.signals.failed.emit(str(exc))
