"""Lightweight biomedical filters for display + analysis."""

from __future__ import annotations

import numpy as np
from scipy import signal
from scipy.ndimage import median_filter


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

def _interp_invalid(data: np.ndarray) -> np.ndarray:
    x = np.asarray(data, dtype=np.float64).copy()
    invalid = ~np.isfinite(x)
    if not np.any(invalid):
        return x
    good = np.where(~invalid)[0]
    bad = np.where(invalid)[0]
    if len(good) == 0:
        return np.zeros_like(x)
    x[bad] = np.interp(bad, good, x[good])
    return x


def bandpass(data: np.ndarray, fs: float, low: float, high: float, order: int = 2) -> np.ndarray:
    x = _interp_invalid(data)
    if len(x) < 16:
        return x
    nyq = 0.5 * fs
    high = min(high, nyq * 0.95)
    if low <= 0 or high <= low:
        return x
    sos = signal.butter(order, [low, high], btype="bandpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x)


def lowpass(data: np.ndarray, fs: float, cutoff: float, order: int = 2) -> np.ndarray:
    x = _interp_invalid(data)
    if len(x) < 16:
        return x
    nyq = 0.5 * fs
    cutoff = min(float(cutoff), nyq * 0.95)
    if cutoff <= 0:
        return x
    sos = signal.butter(order, cutoff, btype="lowpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x)


def moving_average(data: np.ndarray, n: int) -> np.ndarray:
    x = _interp_invalid(data)
    n = max(1, int(n))
    if n <= 1 or len(x) < n:
        return x
    kernel = np.ones(n, dtype=np.float64) / n
    return np.convolve(x, kernel, mode="same")


# ---------------------------------------------------------------------------
# Analysis filters (metrics worker)
# ---------------------------------------------------------------------------

def filter_ecg(data: np.ndarray, fs: float) -> np.ndarray:
    x = _interp_invalid(data)
    x = median_filter(x, size=3)
    return bandpass(x, fs, 0.5, min(40.0, 0.45 * fs), order=2)


def filter_ppg(data: np.ndarray, fs: float, invert: bool = True) -> np.ndarray:
    """PPG AC extraction for SpO2 / pulse analysis."""
    x = _interp_invalid(data)
    x = median_filter(x, size=5)
    x = signal.detrend(x, type="linear")
    x = bandpass(x, fs, 0.5, min(5.0, 0.45 * fs), order=2)
    if invert:
        x = -x
    return x


def filter_rsp(data: np.ndarray, fs: float) -> np.ndarray:
    """
    Analysis RSP: light de-quantization + breathing band.
    Keeps infant RR content (~6–90 bpm → 0.1–1.5 Hz).
    """
    x = dequantize_rsp(data, fs)
    return bandpass(x, fs, 0.08, min(1.5, 0.45 * fs), order=2)


def dequantize_rsp(data: np.ndarray, fs: float) -> np.ndarray:
    """
    Remove stair-step / hold quantization only — no heavy low-pass.
    Short median + ~80 ms average.
    """
    x = _interp_invalid(data)
    med = max(3, int(round(fs * 0.05)))  # ~50 ms
    if med % 2 == 0:
        med += 1
    x = median_filter(x, size=med)
    return moving_average(x, max(3, int(round(fs * 0.08))))


# ---------------------------------------------------------------------------
# Display preprocessing (user-selectable modes)
# ---------------------------------------------------------------------------

ECG_PREP_MODES = (
    ("raw", "Raw"),
    ("bandpass", "Bandpass 0.5–40 Hz"),
)

PPG_PREP_MODES = (
    ("raw", "Raw"),
    ("invert", "Invert polarity"),
    ("ac", "AC (remove DC)"),
    ("ac_invert", "AC + invert"),
)

RSP_PREP_MODES = (
    ("raw", "Raw"),
    ("dequantize", "De-quantize (light)"),
    ("bandpass", "Breathing band (light)"),
)


def _local_remove_dc(x: np.ndarray, fs: float, win_s: float = 1.25) -> np.ndarray:
    """
    Centered moving-average high-pass with reflect padding.

    Avoids filtfilt edge bounce *and* causal EMA cold-start on every redraw of
    a sliding plot window (both look like amplitude jumps at left/right).
    """
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 8:
        return x.copy()
    win = max(5, int(round(fs * win_s)))
    if win % 2 == 0:
        win += 1
    win = min(win, len(x) if len(x) % 2 == 1 else len(x) - 1)
    win = max(5, win)
    pad = win // 2
    xp = np.pad(x, pad, mode="reflect")
    kernel = np.ones(win, dtype=np.float64) / float(win)
    dc = np.convolve(xp, kernel, mode="valid")
    if len(dc) != len(x):
        # Defensive: fall back to global demean
        return x - float(np.mean(x))
    return x - dc


def _smooth_causal(x: np.ndarray, fs: float, cutoff: float) -> np.ndarray:
    """One-way Butterworth LP (no filtfilt edge amplification)."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 16:
        return x
    nyq = 0.5 * fs
    cutoff = min(float(cutoff), nyq * 0.95)
    if cutoff <= 0:
        return x
    sos = signal.butter(2, cutoff, btype="lowpass", fs=fs, output="sos")
    return signal.sosfilt(sos, x)


def prepare_ecg_display(data: np.ndarray, fs: float, mode: str = "bandpass") -> np.ndarray:
    x = _interp_invalid(data)
    if mode == "raw" or len(x) < 16:
        return x
    y = _local_remove_dc(x, fs, win_s=0.6)
    return _smooth_causal(y, fs, cutoff=min(40.0, 0.45 * fs))


def prepare_ppg_display(data: np.ndarray, fs: float, mode: str = "ac_invert") -> np.ndarray:
    """
    PPG scope prep. AC modes use *local* DC removal (reflect-padded MA) so
    scrolling windows don't jump at the left/right edges.
    """
    x = _interp_invalid(data)
    if len(x) < 8:
        return x

    if mode == "raw":
        return x

    if mode == "invert":
        return -median_filter(x, size=3)

    # Light despike, then local AC — keeps pulse shape + beat-to-beat variety
    ac = _local_remove_dc(median_filter(x, size=3), fs, win_s=1.2)
    # Soft causal LP only (grain); skip filtfilt which reintroduces edge bounce
    if len(ac) >= int(fs):
        ac = _smooth_causal(ac, fs, cutoff=min(12.0, 0.45 * fs))
    if mode == "ac_invert":
        ac = -ac
    if float(np.nanstd(ac)) < 1e-9:
        return -median_filter(x, size=3) if mode == "ac_invert" else median_filter(x, size=3)
    return ac


def prepare_rsp_display(data: np.ndarray, fs: float, mode: str = "dequantize") -> np.ndarray:
    x = _interp_invalid(data)
    if mode == "raw" or len(x) < 8:
        return x
    if mode == "bandpass":
        y = dequantize_rsp(x, fs)
        y = _local_remove_dc(y, fs, win_s=6.0)
        return _smooth_causal(y, fs, cutoff=min(1.5, 0.45 * fs))
    return dequantize_rsp(x, fs)


# Back-compat aliases used earlier
def ppg_for_display(data: np.ndarray, fs: float) -> np.ndarray:
    return prepare_ppg_display(data, fs, mode="invert")


def rsp_for_display(data: np.ndarray, fs: float) -> np.ndarray:
    return prepare_rsp_display(data, fs, mode="dequantize")
