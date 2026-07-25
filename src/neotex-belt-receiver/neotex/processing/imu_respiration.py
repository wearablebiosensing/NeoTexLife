"""Streaming IMU → respiration extraction (Acc + Gyro), sample-efficient."""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi


class CausalBandpass:
    """Stateful SOS bandpass for chunked / sample streaming."""

    __slots__ = ("sos", "zi")

    def __init__(self, fs: float, low: float, high: float, order: int = 2):
        nyq = 0.5 * fs
        high = min(float(high), nyq * 0.95)
        low = max(float(low), 0.01)
        if high <= low:
            high = min(low + 0.2, nyq * 0.95)
        self.sos = butter(order, [low, high], btype="bandpass", fs=fs, output="sos")
        self.zi = sosfilt_zi(self.sos) * 0.0

    def reset(self, x0: float = 0.0) -> None:
        self.zi = sosfilt_zi(self.sos) * float(x0)

    def process(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64).reshape(-1)
        if x.size == 0:
            return x
        y, self.zi = sosfilt(self.sos, x, zi=self.zi)
        return y


class StreamingIMURespiration:
    """
    Extract a respiration waveform from triaxial Acc + Gyro every sample.

    Method (chest / belt wearable, causal & cheap):
      1. EMA gravity estimate from Acc
      2. Acc proxy  = projection of Acc onto gravity axis (thoracic modulation)
      3. Gyro proxy = |Gyro| with slow EMA removed
      4. Causal bandpass both into infant breathing band (~0.08–1.2 Hz)
      5. Fuse with adaptive gains (rolling std normalization)

    Designed for ~100 Hz belt streams; ``process_chunk`` is the hot path.
    """

    def __init__(
        self,
        fs: float = 100.0,
        gravity_tau_s: float = 1.5,
        gyro_dc_tau_s: float = 2.0,
        low_hz: float = 0.08,
        high_hz: float = 1.2,
        acc_weight: float = 0.7,
    ):
        self.fs = float(fs)
        self.dt = 1.0 / self.fs
        self.acc_weight = float(np.clip(acc_weight, 0.0, 1.0))
        self.gyro_weight = 1.0 - self.acc_weight

        # EMA coefficients: y += a*(x-y)
        self._a_g = 1.0 - np.exp(-self.dt / max(gravity_tau_s, 1e-3))
        self._a_gyro_dc = 1.0 - np.exp(-self.dt / max(gyro_dc_tau_s, 1e-3))

        self._g = np.zeros(3, dtype=np.float64)
        self._g_ready = False
        self._gyro_dc = 0.0
        self._gyro_dc_ready = False

        self._bp_acc = CausalBandpass(self.fs, low_hz, high_hz, order=2)
        self._bp_gyro = CausalBandpass(self.fs, low_hz, high_hz, order=2)

        # Rolling power for fusion normalization (EMA of |signal|)
        self._acc_amp = 1.0
        self._gyro_amp = 1.0
        self._a_amp = 1.0 - np.exp(-self.dt / 3.0)

        self._n = 0

    def reset(self) -> None:
        self._g[:] = 0.0
        self._g_ready = False
        self._gyro_dc = 0.0
        self._gyro_dc_ready = False
        self._bp_acc.reset(0.0)
        self._bp_gyro.reset(0.0)
        self._acc_amp = 1.0
        self._gyro_amp = 1.0
        self._n = 0

    def set_sampling_rate(self, fs: float) -> None:
        """Rebuild filters if fs changes (e.g. new file)."""
        if abs(float(fs) - self.fs) < 1e-6:
            return
        cfg = dict(
            gravity_tau_s=1.5,
            gyro_dc_tau_s=2.0,
            low_hz=0.08,
            high_hz=1.2,
            acc_weight=self.acc_weight,
        )
        self.__init__(fs=fs, **cfg)

    def process_chunk(
        self,
        acc: np.ndarray,
        gyro: np.ndarray,
    ) -> np.ndarray:
        """
        Parameters
        ----------
        acc : (N, 3) AccX/Y/Z
        gyro : (N, 3) GyroX/Y/Z

        Returns
        -------
        resp : (N,) fused IMU respiration waveform
        """
        acc = np.asarray(acc, dtype=np.float64)
        gyro = np.asarray(gyro, dtype=np.float64)
        if acc.ndim != 2 or acc.shape[1] < 3:
            raise ValueError("acc must be shaped (N, 3)")
        if gyro.ndim != 2 or gyro.shape[1] < 3:
            raise ValueError("gyro must be shaped (N, 3)")
        n = min(len(acc), len(gyro))
        if n == 0:
            return np.empty(0, dtype=np.float64)

        acc_proxy = np.empty(n, dtype=np.float64)
        gyro_proxy = np.empty(n, dtype=np.float64)

        for i in range(n):
            a = acc[i, :3]
            gyr = gyro[i, :3]

            # --- Acc: gravity-aligned thoracic component ---
            if not self._g_ready:
                self._g = a.copy()
                self._g_ready = True
            else:
                self._g += self._a_g * (a - self._g)

            g_norm = float(np.linalg.norm(self._g))
            if g_norm < 1e-6:
                acc_proxy[i] = 0.0
            else:
                # Projection along gravity; remove static |g|
                acc_proxy[i] = float(np.dot(a, self._g) / g_norm) - g_norm

            # --- Gyro: magnitude after slow DC removal ---
            gmag = float(np.linalg.norm(gyr))
            if not self._gyro_dc_ready:
                self._gyro_dc = gmag
                self._gyro_dc_ready = True
            else:
                self._gyro_dc += self._a_gyro_dc * (gmag - self._gyro_dc)
            gyro_proxy[i] = gmag - self._gyro_dc

        acc_bp = self._bp_acc.process(acc_proxy)
        gyro_bp = self._bp_gyro.process(gyro_proxy)

        out = np.empty(n, dtype=np.float64)
        for i in range(n):
            self._acc_amp += self._a_amp * (abs(acc_bp[i]) - self._acc_amp)
            self._gyro_amp += self._a_amp * (abs(gyro_bp[i]) - self._gyro_amp)
            a_s = acc_bp[i] / max(self._acc_amp, 1e-6)
            g_s = gyro_bp[i] / max(self._gyro_amp, 1e-6)
            out[i] = self.acc_weight * a_s + self.gyro_weight * g_s

        self._n += n
        return out


def extract_imu_respiration_batch(
    acc: np.ndarray,
    gyro: np.ndarray,
    fs: float = 100.0,
) -> np.ndarray:
    """Offline convenience wrapper (same algorithm, fresh state)."""
    eng = StreamingIMURespiration(fs=fs)
    return eng.process_chunk(acc, gyro)
