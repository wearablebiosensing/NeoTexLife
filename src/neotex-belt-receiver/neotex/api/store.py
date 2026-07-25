"""Thread-safe vitals store shared by the GUI and FastAPI."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Optional


class VitalsStore:
    def __init__(self, history_size: int = 256):
        self._lock = threading.RLock()
        self._latest: Optional[dict[str, Any]] = None
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._status: dict[str, Any] = {
            "streaming": False,
            "file": None,
            "api_started_at": time.time(),
        }

    def publish(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._latest = payload
            self._history.append(payload)

    def set_status(self, **kwargs) -> None:
        with self._lock:
            self._status.update(kwargs)

    def latest(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return None if self._latest is None else dict(self._latest)

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        if limit > 0:
            items = items[-limit:]
        return items

    def status(self) -> dict[str, Any]:
        with self._lock:
            st = dict(self._status)
            st["history_len"] = len(self._history)
            st["has_latest"] = self._latest is not None
            return st


# Process-wide singleton used by FastAPI + GUI
STORE = VitalsStore()