"""Background worker threads for long-running operations."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class CrawlWorker(QThread):
    progress = Signal(str)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancel = threading.Event()
        self.pause_event = threading.Event()

    def run(self) -> None:
        kwargs = dict(self._kwargs)
        kwargs["progress_callback"] = self.progress.emit
        kwargs["cancel_check"] = self._cancel.is_set
        kwargs["pause_event"] = self.pause_event
        try:
            self.result.emit(self._fn(*self._args, **kwargs))
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))

    def cancel(self) -> None:
        self._cancel.set()
        self.pause_event.clear()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()


class AnalyzeWorker(QThread):
    progress = Signal(str)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancel = threading.Event()

    def run(self) -> None:
        kwargs = dict(self._kwargs)
        kwargs["progress_callback"] = self.progress.emit
        kwargs["cancel_check"] = self._cancel.is_set
        try:
            self.result.emit(self._fn(*self._args, **kwargs))
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))

    def cancel(self) -> None:
        self._cancel.set()

