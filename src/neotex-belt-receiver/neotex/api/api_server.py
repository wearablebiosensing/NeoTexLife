"""Background uvicorn runner for embedding FastAPI inside the PyQt app."""

from __future__ import annotations

import threading
from typing import Optional

import uvicorn
from PyQt5.QtCore import QObject, pyqtSignal

from neotex.api.server import create_app
from neotex.constants import API_HOST, API_PORT


class ApiServerWorker(QObject):
    status = pyqtSignal(str)

    def __init__(self, host: str = API_HOST, port: int = API_PORT):
        super().__init__()
        self.host = host
        self.port = port
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        config = uvicorn.Config(
            create_app(),
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        def _run():
            self.status.emit(f"FastAPI listening on {self.base_url}")
            assert self._server is not None
            self._server.run()

        self._thread = threading.Thread(target=_run, name="neotex-fastapi", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            self.status.emit("FastAPI stopping")
        self._server = None
        self._thread = None