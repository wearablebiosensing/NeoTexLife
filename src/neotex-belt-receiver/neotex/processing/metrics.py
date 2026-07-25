"""Live vitals extraction (HR, RR, SpO2, Temp) via NeuroKit2 + PPG ratio."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from neotex.processing.filters import filter_ecg, filter_ppg, filter_rsp


def _round(v: Optional[float], nd: int = 1) -> Optional[float]:
    if v is None or not np.isfinite(v):
        return None
    return round(float(v), nd)


def compute_spo2_from_ppg(
    red: np.ndarray,
    ir: np.ndarray,
    fs: float,
) -> Optional[float]:
    """
    Estimate SpO2 from Red/IR using ratio-of-ratios on short stable windows.

    R = (σ_red / μ_red) / (σ_ir / μ_ir)
    SpO2 ≈ 110 − 25·R   (demo calibration)

    Rejects windows with pathological AC (motion / LED dropouts). Falls back
    to None when no reliable window exists.
    """
    red = np.asarray(red, dtype=np.float64)
    ir = np.asarray(ir, dtype=np.float64)
    n = min(len(red), len(ir))
    if n < int(fs * 3):
        return None

    red = red[-n:]
    ir = ir[-n:]
    win = max(int(fs * 3), 50)
    hop = max(int(fs * 1.0), 25)
    estimates: list[float] = []

    for start in range(0, n - win + 1, hop):
        r = red[start : start + win]
        i = ir[start : start + win]
        r_mean = float(np.mean(r))
        i_mean = float(np.mean(i))
        if abs(r_mean) < 1e-3 or abs(i_mean) < 1e-3:
            continue

        r_ac = filter_ppg(r, fs)
        i_ac = filter_ppg(i, fs)
        r_amp = float(np.std(r_ac))
        i_amp = float(np.std(i_ac))
        if i_amp < 1e-3 or r_amp < 1e-3:
            continue

        # Reject if one channel's AC dwarfs the other (dropout / motion)
        ratio_amps = r_amp / i_amp
        if ratio_amps < 0.05 or ratio_amps > 20.0:
            continue

        r_ratio = (r_amp / abs(r_mean)) / (i_amp / abs(i_mean))
        if not (0.3 <= r_ratio <= 2.5):
            continue

        spo2 = 110.0 - 25.0 * r_ratio
        if 70.0 <= spo2 <= 100.0:
            estimates.append(float(spo2))

    if not estimates:
        return None
    return float(np.median(estimates))


def compute_hr_from_ecg(ecg: np.ndarray, fs: float) -> dict[str, Any]:
    import neurokit2 as nk

    cleaned = filter_ecg(ecg, fs)
    try:
        cleaned = nk.ecg_clean(cleaned, sampling_rate=fs)
    except Exception:
        pass

    r_peaks: np.ndarray = np.array([], dtype=int)
    sqi = None
    try:
        _, info = nk.ecg_peaks(cleaned, sampling_rate=fs)
        r_peaks = np.asarray(info.get("ECG_R_Peaks", []), dtype=int)
    except Exception:
        r_peaks = np.array([], dtype=int)

    hr = None
    if len(r_peaks) >= 2:
        rr = np.diff(r_peaks) / fs
        # Neonate-aware bounds: ~60–220 bpm
        valid = rr[(rr > 60.0 / 220.0) & (rr < 60.0 / 50.0)]
        if len(valid):
            hr = float(60.0 / np.mean(valid))
        try:
            q = nk.ecg_quality(cleaned, rpeaks=r_peaks, sampling_rate=fs)
            sqi = float(np.nanmean(q))
        except Exception:
            sqi = None

    return {
        "hr_bpm": _round(hr, 1),
        "n_r_peaks": int(len(r_peaks)),
        "ecg_sqi": _round(sqi, 3) if sqi is not None else None,
        "ecg_clean": cleaned,
    }


def compute_rr_from_rsp(rsp: np.ndarray, fs: float) -> dict[str, Any]:
    import neurokit2 as nk

    cleaned = filter_rsp(rsp, fs)
    rate = None
    n_peaks = 0
    try:
        signals, info = nk.rsp_process(cleaned, sampling_rate=fs)
        peaks = np.asarray(info.get("RSP_Peaks", []), dtype=int)
        n_peaks = int(len(peaks))
        if "RSP_Rate" in signals.columns:
            rates = signals["RSP_Rate"].to_numpy(dtype=np.float64)
            rates = rates[np.isfinite(rates) & (rates > 4) & (rates < 120)]
            if len(rates):
                rate = float(np.median(rates))
        if rate is None and n_peaks >= 2:
            ibi = np.diff(peaks) / fs
            ibi = ibi[(ibi > 0.4) & (ibi < 12.0)]
            if len(ibi):
                rate = float(60.0 / np.mean(ibi))
        cleaned_out = (
            signals["RSP_Clean"].to_numpy(dtype=np.float64)
            if "RSP_Clean" in signals.columns
            else cleaned
        )
    except Exception:
        cleaned_out = cleaned

    return {
        "rr_bpm": _round(rate, 1),
        "n_rsp_peaks": n_peaks,
        "rsp_clean": cleaned_out,
    }


def compute_temperature(temp: np.ndarray) -> Optional[float]:
    if temp is None or len(temp) == 0:
        return None
    x = np.asarray(temp, dtype=np.float64)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
    # Belt dumps appear to be °F already (~85–100). Keep as-is.
    return _round(float(np.median(x)), 1)


def extract_vitals(
    *,
    ecg: np.ndarray,
    rsp: np.ndarray,
    red: np.ndarray,
    ir: np.ndarray,
    temp: np.ndarray,
    fs: float,
    device_hr: Optional[np.ndarray] = None,
    device_spo2: Optional[np.ndarray] = None,
) -> dict[str, Any]:
    """Run the full 5 s / rolling-window vitals pipeline."""
    hr_info = compute_hr_from_ecg(ecg, fs)
    rr_info = compute_rr_from_rsp(rsp, fs)
    spo2 = compute_spo2_from_ppg(red, ir, fs)
    temperature = compute_temperature(temp)

    # Prefer computed SpO2; if AC is weak, fall back to plausible device SpO2.
    if spo2 is None and device_spo2 is not None:
        ds = np.asarray(device_spo2, dtype=np.float64)
        ds = ds[np.isfinite(ds) & (ds >= 70) & (ds <= 100)]
        if len(ds):
            spo2 = _round(float(np.median(ds)), 1)

    # If ECG HR fails, fall back to device HR when plausible.
    if hr_info["hr_bpm"] is None and device_hr is not None:
        dh = np.asarray(device_hr, dtype=np.float64)
        dh = dh[np.isfinite(dh) & (dh > 40) & (dh < 230)]
        if len(dh):
            hr_info["hr_bpm"] = _round(float(np.median(dh)), 1)

    return {
        "hr_bpm": hr_info["hr_bpm"],
        "rr_bpm": rr_info["rr_bpm"],
        "spo2_pct": _round(spo2, 1) if spo2 is not None else None,
        "temp_f": temperature,
        "quality": {
            "ecg_sqi": hr_info["ecg_sqi"],
            "n_r_peaks": hr_info["n_r_peaks"],
            "n_rsp_peaks": rr_info["n_rsp_peaks"],
        },
        "cleaned": {
            "ecg": hr_info["ecg_clean"],
            "rsp": rr_info["rsp_clean"],
            "ppg_ir": filter_ppg(ir, fs),
            "ppg_red": filter_ppg(red, fs),
        },
    }