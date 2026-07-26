"""NeuroKit2 metrics worker — emits vitals every METRICS_INTERVAL_S seconds."""

from __future__ import annotations

import time
from collections import deque

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from neotex.constants import (
    METRICS_ANALYSIS_WINDOW_S,
    METRICS_INTERVAL_S,
    SAMPLING_RATE_HZ,
)
from neotex.processing.metrics import extract_vitals


class ProcessingWorker(QObject):
    """
    Consumes raw belt samples and periodically computes live vitals.

    Signals
    -------
    vitals_result(dict)  — packaged metrics + unix_timestamp
    status(str)
    """

    vitals_result = pyqtSignal(object)
    status = pyqtSignal(str)

    def __init__(self, fs: float = SAMPLING_RATE_HZ, buffer_seconds: float = 60.0):
        super().__init__()
        self._fs = float(fs)
        self._running = False
        maxlen = int(self._fs * buffer_seconds)
        self._ecg = deque(maxlen=maxlen)
        self._rsp0 = deque(maxlen=maxlen)
        self._rsp1 = deque(maxlen=maxlen)
        self._rsp_imu = deque(maxlen=maxlen)
        self._ir = deque(maxlen=maxlen)
        self._red = deque(maxlen=maxlen)
        self._temp = deque(maxlen=maxlen)
        self._device_hr = deque(maxlen=maxlen)
        self._device_spo2 = deque(maxlen=maxlen)
        self._last_metrics_t = 0.0
        self._source_file = ""
        self._analysis_n = int(self._fs * METRICS_ANALYSIS_WINDOW_S)
        # auto | resp0 | resp1 | imu
        self._rr_source = "auto"

    def set_rr_source(self, source: str) -> None:
        src = (source or "auto").lower()
        if src not in ("auto", "resp0", "resp1", "imu"):
            src = "auto"
        self._rr_source = src

    def set_sampling_rate(self, fs: float) -> None:
        self._fs = float(fs)
        self._analysis_n = int(self._fs * METRICS_ANALYSIS_WINDOW_S)

    def set_source_file(self, path: str) -> None:
        self._source_file = path

    def clear(self) -> None:
        for buf in (
            self._ecg,
            self._rsp0,
            self._rsp1,
            self._rsp_imu,
            self._ir,
            self._red,
            self._temp,
            self._device_hr,
            self._device_spo2,
        ):
            buf.clear()
        self._last_metrics_t = 0.0

    def add_chunk(self, chunk: dict) -> None:
        self._ecg.extend(chunk["ecg"])
        self._rsp0.extend(chunk.get("resp0", chunk.get("resp", [])))
        self._rsp1.extend(chunk.get("resp1", chunk.get("resp", [])))
        if "resp_imu" in chunk:
            self._rsp_imu.extend(chunk["resp_imu"])
        self._ir.extend(chunk["ir"])
        self._red.extend(chunk["red"])
        self._temp.extend(chunk["temp"])
        self._device_hr.extend(chunk["device_hr"])
        self._device_spo2.extend(chunk["device_spo2"])

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True
        self.status.emit("Metrics worker started")
        try:
            import os

            os.environ.setdefault("MPLBACKEND", "Agg")
            import matplotlib

            matplotlib.use("Agg")
            import neurokit2 as nk  # noqa: F401

            self.status.emit("NeuroKit2 ready")
        except Exception as exc:
            self.status.emit(f"NeuroKit2 warm-up warning: {exc}")

        while self._running:
            self._maybe_compute()
            time.sleep(0.05)
        self.status.emit("Metrics worker stopped")

    def _snap(self, buf: deque, n: int) -> np.ndarray:
        if len(buf) < n:
            return np.asarray(buf, dtype=np.float64)
        return np.asarray(list(buf)[-n:], dtype=np.float64)

    def _pick_rsp(self, n: int) -> tuple[np.ndarray, str]:
        r0 = self._snap(self._rsp0, n)
        r1 = self._snap(self._rsp1, n)
        rimu = self._snap(self._rsp_imu, n)

        if self._rr_source == "resp0":
            return r0, "resp0"
        if self._rr_source == "resp1":
            return r1, "resp1"
        if self._rr_source == "imu":
            return rimu if len(rimu) else r0, "imu"

        # Auto: best capacitive channel (IMU kept for optional backend use only)
        candidates: list[tuple[str, np.ndarray, float]] = [
            ("resp0", r0, float(np.nanstd(r0))),
            ("resp1", r1, float(np.nanstd(r1))),
        ]
        best_name, best_arr, best_std = candidates[0]
        for name, arr, std in candidates[1:]:
            if std > best_std:
                best_name, best_arr, best_std = name, arr, std
        return best_arr, best_name

    def _maybe_compute(self) -> None:
        now = time.time()
        if now - self._last_metrics_t < METRICS_INTERVAL_S:
            return
        min_n = int(self._fs * 8)
        if len(self._ecg) < min_n:
            return

        self._last_metrics_t = now
        n = min(self._analysis_n, len(self._ecg))
        rsp, rsp_used = self._pick_rsp(n)

        try:
            result = extract_vitals(
                ecg=self._snap(self._ecg, n),
                rsp=rsp,
                red=self._snap(self._red, n),
                ir=self._snap(self._ir, n),
                temp=self._snap(self._temp, n),
                fs=self._fs,
                device_hr=self._snap(self._device_hr, n),
                device_spo2=self._snap(self._device_spo2, n),
            )
            cleaned = result.pop("cleaned", {})
            payload = {
                "unix_timestamp": now,
                "window_s": METRICS_INTERVAL_S,
                "analysis_window_s": n / self._fs,
                "sampling_rate_hz": self._fs,
                "source": "file_playback",
                "file": self._source_file,
                "rr_source": rsp_used,
                "vitals": {
                    "hr_bpm": result["hr_bpm"],
                    "rr_bpm": result["rr_bpm"],
                    "spo2_pct": result["spo2_pct"],
                    "temp_f": result["temp_f"],
                },
                "quality": result["quality"],
                "preview": {
                    "ecg_n": int(len(cleaned.get("ecg", []))),
                    "rsp_n": int(len(cleaned.get("rsp", []))),
                },
            }
            self.vitals_result.emit(payload)
        except Exception as exc:
            self.vitals_result.emit(
                {
                    "unix_timestamp": now,
                    "window_s": METRICS_INTERVAL_S,
                    "source": "file_playback",
                    "file": self._source_file,
                    "rr_source": rsp_used,
                    "vitals": {
                        "hr_bpm": None,
                        "rr_bpm": None,
                        "spo2_pct": None,
                        "temp_f": None,
                    },
                    "quality": {},
                    "error": str(exc),
                }
            )
