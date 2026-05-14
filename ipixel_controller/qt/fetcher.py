"""Tiny background-fetch helper for the Qt UI.

Runs a blocking callable in a thread and re-emits its result via Qt
signals so the UI thread stays responsive. Used by the Stock / YouTube /
Weather pages — each of which calls a synchronous Python library.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal


class BackgroundFetcher(QObject):
    """Wraps ``fn(**kwargs) -> Any`` so callers can connect Qt slots."""

    started = Signal()
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[..., Any]) -> None:
        super().__init__()
        self._fn = fn

    def run(self, **kwargs: Any) -> None:
        self.started.emit()

        def task() -> None:
            try:
                result = self._fn(**kwargs)
                self.succeeded.emit(result)
            except Exception as e:  # noqa: BLE001
                self.failed.emit(str(e))

        threading.Thread(target=task, daemon=True).start()
