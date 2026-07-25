"""File playback worker — streams CSV samples at the recording's native rate."""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from neotex.constants import CHUNK_SAMPLES
from neotex.utils.data_loader import BeltRecording, load_belt_csv


class PlaybackWorker(QThread):
    """
    Mimics a USB COM livestream by pacing CSV rows at sampling_rate Hz.

    Emits sample chunks to keep GUI / processing queues light:
      samples_chunk(dict)  — keys: ecg, resp0, resp1, resp, ir, red, temp, …
      status(str)
      finished_playback()  — end of file (does not auto-loop unless restart() called)
      progress(float)      — 0..1
    """

    samples_chunk = pyqtSignal(object)
    status = pyqtSignal(str)
    finished_playback = pyqtSignal()
    progress = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording: Optional[BeltRecording] = None
        self._running = False
        self._paused = False
        self._index = 0
        self._speed = 1.0
        self._loop = True
        self._chunk = CHUNK_SAMPLES

    # ------------------------------------------------------------------ #
    #  Control API (thread-safe enough for Qt main-thread callers)
    # ------------------------------------------------------------------ #

    def load_file(self, path: str, sampling_rate: Optional[float] = None) -> BeltRecording:
        rec = load_belt_csv(path, sampling_rate=sampling_rate)
        self._recording = rec
        self._index = 0
        self.status.emit(
            f"Loaded {rec.path.name} · {rec.n_samples} samples · "
            f"{rec.sampling_rate:.0f} Hz · {rec.duration_s:.1f}s"
        )
        return rec

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.1, float(speed))

    def set_loop(self, loop: bool) -> None:
        self._loop = bool(loop)

    def pause(self) -> None:
        self._paused = True
        self.status.emit("Playback paused")

    def resume(self) -> None:
        self._paused = False
        self.status.emit("Playback resumed")

    def restart(self) -> None:
        self._index = 0
        self._paused = False
        self.status.emit("Playback restarted")

    def stop(self) -> None:
        self._running = False

    @property
    def recording(self) -> Optional[BeltRecording]:
        return self._recording

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self._running = True
        if self._recording is None:
            self.status.emit("No file loaded")
            self._running = False
            return

        rec = self._recording
        fs = rec.sampling_rate
        chunk = max(1, int(self._chunk))
        period = chunk / (fs * self._speed)

        self.status.emit(f"Streaming @ {fs:.0f} Hz (chunk={chunk})")
        next_t = time.perf_counter()

        while self._running:
            if self._paused:
                time.sleep(0.05)
                next_t = time.perf_counter()
                continue

            if self._index >= rec.n_samples:
                if self._loop:
                    self._index = 0
                    self.status.emit("Looping playback")
                else:
                    self.progress.emit(1.0)
                    self.finished_playback.emit()
                    break

            end = min(self._index + chunk, rec.n_samples)
            sl = slice(self._index, end)
            n = end - self._index

            payload = {
                "ecg": rec.ecg[sl].copy(),
                "resp0": rec.resp0[sl].copy(),
                "resp1": rec.resp1[sl].copy(),
                "resp": rec.resp[sl].copy(),  # best capacitive for metrics fallback
                "ir": rec.ir[sl].copy(),
                "red": rec.red[sl].copy(),
                "temp": rec.temp[sl].copy(),
                "device_hr": rec.device_hr[sl].copy(),
                "device_spo2": rec.device_spo2[sl].copy(),
                "acc": rec.acc[sl].copy(),
                "gyro": rec.gyro[sl].copy(),
                "t0": self._index / fs,
                "n": n,
                "fs": fs,
            }
            self.samples_chunk.emit(payload)
            self._index = end
            self.progress.emit(self._index / rec.n_samples)

            next_t += period
            sleep_for = next_t - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # Behind schedule — catch up without spinning
                next_t = time.perf_counter()

        self._running = False
        self.status.emit("Playback stopped")