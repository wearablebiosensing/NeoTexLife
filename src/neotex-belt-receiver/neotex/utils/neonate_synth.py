"""
Demo belt telemetry from *real* adult biosignals, time-compressed.

Source: NeuroKit2 ``bio_resting_5min_100hz`` (ECG + PPG + RSP @ 100 Hz).
We speed up time so adult HR/RR approach neonatal demo rates, then pack into
the NeoTex baby-belt CSV schema (Red/IR, dual Resp, Acc/Gyro, Temp).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import signal as spsig

from neotex.constants import DEFAULT_SAMPLE_DIR, SAMPLING_RATE_HZ
from neotex.utils.data_loader import BeltRecording


@dataclass(frozen=True)
class RealBioDemoConfig:
    duration_s: float = 180.0
    sampling_rate: float = float(SAMPLING_RATE_HZ)
    # Target neonatal-ish HR; speed factor derived from measured adult HR
    target_hr_bpm: float = 140.0
    # Soft clamp on speed-up (avoid extreme resampling artifacts)
    max_speed: float = 2.2
    min_speed: float = 1.2
    spo2_pct: float = 98.0
    temp_f: float = 98.6
    seed: int = 42


def _normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    s = float(np.std(x))
    if s < 1e-12:
        return np.zeros_like(x)
    return (x - float(np.mean(x))) / s


def _fit_len(a: np.ndarray, n: int) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    if len(a) >= n:
        return a[:n].copy()
    out = np.zeros(n, dtype=np.float64)
    if len(a) == 0:
        return out
    out[: len(a)] = a
    out[len(a) :] = a[-1]
    return out


def _tile(a: np.ndarray, n: int) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    if len(a) == 0:
        return np.zeros(n, dtype=np.float64)
    reps = int(np.ceil(n / len(a)))
    return np.tile(a, reps)[:n]


def _speed_up(x: np.ndarray, speed: float) -> np.ndarray:
    """
    Compress time by ``speed`` (faster rhythms).

    Prefer polyphase resample (keeps PPG morphology better than FFT resample,
    which over-smooths into sine-like pulses).
    """
    x = np.asarray(x, dtype=np.float64)
    speed = float(max(speed, 1.01))
    new_len = max(16, int(round(len(x) / speed)))
    # Rational approximation of new_len/len(x)
    from math import gcd

    g = gcd(new_len, len(x)) or 1
    up, down = new_len // g, len(x) // g
    # Cap large factors — fall back to Fourier if extreme
    if up > 200 or down > 200:
        return spsig.resample(x, new_len)
    try:
        y = spsig.resample_poly(x, up, down)
        return _fit_len(y, new_len) if len(y) != new_len else y
    except Exception:
        return spsig.resample(x, new_len)


def _measure_hr(ecg: np.ndarray, fs: float) -> float:
    import neurokit2 as nk

    try:
        _, info = nk.ecg_peaks(ecg, sampling_rate=fs)
        peaks = np.asarray(info.get("ECG_R_Peaks", []), dtype=int)
        if len(peaks) < 4:
            return float("nan")
        return float(60.0 / np.mean(np.diff(peaks) / fs))
    except Exception:
        return float("nan")


def _load_real_bio(fs: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import neurokit2 as nk

    df = nk.data("bio_resting_5min_100hz")
    ecg = df["ECG"].to_numpy(dtype=np.float64)
    ppg = df["PPG"].to_numpy(dtype=np.float64)
    rsp = df["RSP"].to_numpy(dtype=np.float64)
    # Dataset is already 100 Hz; resample if belt fs differs
    if abs(fs - 100.0) > 0.5:
        n = int(round(len(ecg) * fs / 100.0))
        ecg = spsig.resample(ecg, n)
        ppg = spsig.resample(ppg, n)
        rsp = spsig.resample(rsp, n)
    return ecg, ppg, rsp


def _pink_noise(n: int, rng: np.random.Generator, pole: float = 0.92) -> np.ndarray:
    white = rng.normal(0, 1.0, n)
    pink = spsig.lfilter([1.0], [1.0, -pole], white)
    s = float(np.std(pink)) or 1.0
    return pink / s


def _slow_drift(n: int, fs: float, amp: float, tau_s: float, rng: np.random.Generator) -> np.ndarray:
    """Ornstein–Uhlenbeck-ish slow wander, roughly ±amp."""
    a = float(np.exp(-1.0 / max(fs * tau_s, 1.0)))
    x = np.zeros(n, dtype=np.float64)
    sigma = amp * np.sqrt(max(1.0 - a * a, 1e-6))
    for i in range(1, n):
        x[i] = a * x[i - 1] + sigma * rng.normal()
    # Soft bound
    peak = float(np.percentile(np.abs(x), 99)) or 1.0
    return x * (amp / peak)


def _ppg_shape_with_variety(
    ppg: np.ndarray,
    rsp: np.ndarray,
    fs: float,
    seed: int,
    *,
    am_gain: float = 0.12,
    nonlinear: float = 1.15,
    noise_amp: float = 0.035,
) -> np.ndarray:
    """Real PPG morphology + respiratory AM + grain (channel-tunable)."""
    rng = np.random.default_rng(seed)
    x = np.asarray(ppg, dtype=np.float64)
    n = len(x)
    x = x - float(np.median(x))
    scale = float(np.percentile(np.abs(x), 90)) or 1.0
    shape = x / scale

    breath = _normalize(rsp)
    if len(breath) != n:
        breath = _fit_len(breath, n)
    am = 1.0 + am_gain * breath + 0.04 * np.sin(2 * np.pi * np.arange(n) / (fs * 11.0))

    t = np.arange(n, dtype=np.float64) / fs
    wander = 0.08 * np.sin(2 * np.pi * 0.07 * t + 0.4) + 0.05 * np.sin(
        2 * np.pi * 0.031 * t
    )
    noise = noise_amp * _pink_noise(n, rng) + 0.012 * rng.normal(0, 1.0, n)
    shaped = np.tanh(nonlinear * shape) + 0.08 * shape * np.maximum(shape, 0.0)

    out = shaped * am + wander + noise
    s = float(np.std(out)) or 1.0
    return out / s


def _make_spo2_series(n: int, fs: float, center: float, seed: int) -> np.ndarray:
    """Slow SpO2 wander (~±1.5 around center) with mild plateaus."""
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float64) / fs
    # Multi-minute undulation + OU
    wave = 1.2 * np.sin(2 * np.pi * t / 55.0 + 0.3) + 0.7 * np.sin(2 * np.pi * t / 97.0)
    walk = _slow_drift(n, fs, amp=0.9, tau_s=8.0, rng=rng)
    spo2 = center + wave + walk
    # Occasional brief desat dips (2–4 s)
    n_dips = max(2, int(n / fs / 45.0))
    for _ in range(n_dips):
        c = int(rng.integers(int(2 * fs), max(int(2 * fs) + 1, n - int(3 * fs))))
        half = int(rng.uniform(1.2, 2.5) * fs)
        a, b = max(0, c - half), min(n, c + half)
        env = np.hanning(max(2, b - a))
        spo2[a:b] -= rng.uniform(1.5, 3.5) * env
    return np.clip(spo2, 93.0, 100.0)


def _make_temp_series(n: int, fs: float, center_f: float, seed: int) -> np.ndarray:
    """
    Slow temperature changes totaling ~0.4 °C peak-to-peak (~0.72 °F).
    Belt CSV / UI use °F.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float64) / fs
    amp_f = 0.4 * 9.0 / 5.0  # 0.4 °C → °F peak-to-peak
    # Slow thermal inertia: ~1–2 minute half-cycles
    wave = 0.5 * amp_f * np.sin(2 * np.pi * t / 95.0 + 0.6)
    wave += 0.25 * amp_f * np.sin(2 * np.pi * t / 160.0)
    walk = _slow_drift(n, fs, amp=0.15 * amp_f, tau_s=20.0, rng=rng)
    # Tiny sensor grain only — not beat-to-beat noise
    grain = rng.normal(0, 0.015, n)
    temp = center_f + wave + walk + grain
    # Enforce ~0.4 °C span loosely by rescaling extremes toward target
    span = float(np.percentile(temp, 99) - np.percentile(temp, 1))
    if span > 1e-6:
        target = amp_f
        temp = center_f + (temp - center_f) * (target / span)
    return temp


def _make_red_ir_from_ppg(
    ppg: np.ndarray,
    rsp: np.ndarray,
    spo2_series: np.ndarray,
    fs: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Red/IR from real PPG — channels are intentionally *not* copies:
    different AM, lag, nonlinearity, noise, and DC drift.
    AC ratio tracks ``spo2_series`` so SpO2 can move over time.
    """
    rng = np.random.default_rng(seed)
    n = len(ppg)
    # Shared pulse backbone (same beats) + channel-specific residual so Red ≠ IR copy
    shared = _ppg_shape_with_variety(
        ppg, rsp, fs, seed + 1, am_gain=0.12, nonlinear=1.15, noise_amp=0.02
    )
    red_extra = _ppg_shape_with_variety(
        ppg, rsp, fs, seed + 3, am_gain=0.16, nonlinear=1.3, noise_amp=0.05
    )
    ir_extra = _ppg_shape_with_variety(
        ppg, rsp, fs, seed + 4, am_gain=0.08, nonlinear=1.0, noise_amp=0.025
    )
    shape_red = _normalize(0.78 * shared + 0.22 * red_extra)
    shape_ir = _normalize(0.88 * shared + 0.12 * ir_extra)
    # Extra IR lag vs Red (optical path / filtering)
    lag = max(1, int(0.012 * fs))
    shape_ir = np.roll(shape_ir, lag)
    # IR slightly smoother (more venous / longer wavelength)
    shape_ir = 0.9 * shape_ir + 0.1 * spsig.lfilter([0.2], [1.0, -0.8], shape_ir)
    shape_ir = _normalize(shape_ir)

    spo2 = np.clip(np.asarray(spo2_series, dtype=np.float64), 85.0, 100.0)
    r_ratio = np.clip((110.0 - spo2) / 25.0, 0.35, 1.2)

    dc_ir = 18000.0 + _slow_drift(n, fs, amp=120.0, tau_s=12.0, rng=rng)
    dc_red = 16000.0 + _slow_drift(n, fs, amp=160.0, tau_s=10.0, rng=rng)
    pi_ir = 0.032
    ac_ir = pi_ir * 18000.0
    ac_red = r_ratio * ac_ir * (16000.0 / 18000.0)

    pi_flicker_ir = 1.0 + 0.08 * _slow_drift(n, fs, amp=1.0, tau_s=1.5, rng=rng)
    pi_flicker_red = 1.0 + 0.11 * _slow_drift(n, fs, amp=1.0, tau_s=1.2, rng=rng)

    ir = dc_ir - ac_ir * shape_ir * pi_flicker_ir + rng.normal(0, 12.0, n)
    red = dc_red - ac_red * shape_red * pi_flicker_red + rng.normal(0, 18.0, n)

    t = np.arange(n, dtype=np.float64) / fs
    ir += 55.0 * np.sin(2 * np.pi * 0.02 * t)
    red += 80.0 * np.sin(2 * np.pi * 0.017 * t + 1.1)
    # Channel-specific optical crosstalk residue (small)
    red += 0.04 * (ir - float(np.mean(ir)))
    return red, ir


def _motion_burst_envelope(
    n: int,
    fs: float,
    seed: int,
    n_bursts: Optional[int] = None,
) -> np.ndarray:
    """0–1 envelope of intermittent infant motion (not respiration)."""
    rng = np.random.default_rng(seed)
    env = np.zeros(n, dtype=np.float64)
    dur_s = n / fs
    if n_bursts is None:
        n_bursts = max(4, int(dur_s / 22.0))
    for _ in range(n_bursts):
        c = int(rng.integers(int(fs), max(int(fs) + 1, n - int(fs))))
        half = int(rng.uniform(0.35, 1.8) * fs)
        a, b = max(0, c - half), min(n, c + half)
        w = np.hanning(max(2, b - a))
        # Occasional double-jerk
        strength = float(rng.uniform(0.55, 1.0))
        env[a:b] = np.maximum(env[a:b], strength * w)
        if rng.random() < 0.35 and b + half < n:
            a2, b2 = b, min(n, b + half)
            w2 = np.hanning(max(2, b2 - a2))
            env[a2:b2] = np.maximum(env[a2:b2], 0.7 * strength * w2)
    return np.clip(env, 0.0, 1.0)


def _make_imu_with_breathing(
    rsp: np.ndarray,
    fs: float,
    seed: int,
    motion_env: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, ...]:
    """
    IMU = weak respiratory component + stronger independent motion bursts.
    Returns (acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z).
    """
    rng = np.random.default_rng(seed + 7)
    n = len(rsp)
    t = np.arange(n, dtype=np.float64) / fs
    breath = _normalize(rsp)
    # Don't mirror Cap resp: lag + mild harmonic distortion so quiet IMU ≠ R0
    breath = np.roll(breath, max(1, int(0.18 * fs)))
    breath = 0.75 * breath + 0.25 * np.sign(breath) * (breath ** 2)
    breath = _normalize(breath)
    if motion_env is None:
        motion_env = _motion_burst_envelope(n, fs, seed + 11)
    motion_env = _fit_len(np.asarray(motion_env, dtype=np.float64), n)

    # Broadband motion (not a copy of RSP): filtered noise shaped by envelope
    mx = _pink_noise(n, rng, pole=0.85) * motion_env
    my = _pink_noise(n, rng, pole=0.88) * motion_env
    mz = _pink_noise(n, rng, pole=0.82) * motion_env
    # Sharp jerks inside bursts (+ mid-band energy that survives resp bandpass)
    jerks = rng.normal(0, 1.0, n) * (motion_env ** 1.5)
    mid = _pink_noise(n, rng, pole=0.7) * motion_env

    g = 4096.0
    # Breathing deliberately small vs motion so IMU ≠ Cap resp lookalike
    acc_x = 200.0 + 28.0 * breath + 420.0 * mx + 200.0 * mid + 180.0 * jerks + rng.normal(0, 12, n)
    acc_y = 120.0 + 18.0 * breath + 360.0 * my + 170.0 * mid + 150.0 * jerks + rng.normal(0, 11, n)
    acc_z = (
        g
        + 42.0 * breath
        + 520.0 * mz
        + 240.0 * mid
        + 220.0 * jerks
        + 8.0 * np.sin(2 * np.pi * 0.04 * t)
        + rng.normal(0, 14, n)
    )
    gyro_x = 9.0 * breath + 95.0 * mx + 60.0 * mid + 70.0 * jerks + rng.normal(0, 6, n)
    gyro_y = 14.0 * breath + 110.0 * my + 70.0 * mid + 85.0 * jerks + rng.normal(0, 5, n)
    gyro_z = 6.0 * breath + 70.0 * mz + 50.0 * mid + 55.0 * jerks + rng.normal(0, 5, n)
    return acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z


def _inject_ppg_and_motion_artifacts(
    *,
    ecg: np.ndarray,
    red: np.ndarray,
    ir: np.ndarray,
    resp0: np.ndarray,
    resp1: np.ndarray,
    motion_env: np.ndarray,
    fs: float,
    seed: int,
) -> None:
    """
    In-place: real-ish PPG issues + motion-coupled noise on all bio channels.
    Red and IR get *different* artifact profiles (not a shared copy).
    """
    rng = np.random.default_rng(seed)
    n = len(red)
    env = _fit_len(np.asarray(motion_env, dtype=np.float64), n)

    # --- Motion-coupled noise (when baby moves, everything gets dirtier) ---
    pink = _pink_noise(n, rng)
    ecg += (2800.0 * env) * pink + (900.0 * env) * rng.normal(0, 1.0, n)
    resp0 += (0.55 * env) * _pink_noise(n, rng, 0.9) + 0.15 * env * rng.normal(0, 1, n)
    resp1 += (0.40 * env) * _pink_noise(n, rng, 0.9) + 0.12 * env * rng.normal(0, 1, n)
    # Optical motion artifact — Red usually worse than IR
    red += (520.0 * env) * _pink_noise(n, rng, 0.88) + (180.0 * env) * rng.normal(0, 1, n)
    ir += (280.0 * env) * _pink_noise(n, rng, 0.9) + (90.0 * env) * rng.normal(0, 1, n)

    # --- PPG-specific random issues (independent of IMU bursts) ---
    # 1) Contact / probe lift: AC collapses toward DC for 0.5–2 s (channel-asymmetric)
    for _ in range(max(3, int(n / fs / 35.0))):
        c = int(rng.integers(int(fs), max(int(fs) + 1, n - int(fs))))
        half = int(rng.uniform(0.4, 1.6) * fs)
        a, b = max(0, c - half), min(n, c + half)
        w = np.hanning(max(2, b - a))
        # Prefer Red dropout, sometimes both, rarely IR-only
        which = rng.random()
        if which < 0.55:
            targets = (red,)
        elif which < 0.85:
            targets = (red, ir)
        else:
            targets = (ir,)
        for ch in targets:
            dc = float(np.median(ch[a:b])) if b > a else float(ch[a])
            ch[a:b] = ch[a:b] * (1.0 - 0.85 * w) + dc * (0.85 * w)
            ch[a:b] += rng.normal(0, 25.0, b - a) * w

    # 2) Baseline steps (LED / contact shift) — different size on Red vs IR
    for _ in range(max(2, int(n / fs / 50.0))):
        idx = int(rng.integers(int(0.5 * fs), max(int(0.5 * fs) + 1, n - 1)))
        red[idx:] += rng.uniform(-350, 450)
        ir[idx:] += rng.uniform(-180, 220)

    # 3) Saturation / clip bursts on one channel
    for _ in range(max(1, int(n / fs / 70.0))):
        c = int(rng.integers(int(fs), max(int(fs) + 1, n - int(fs))))
        half = int(rng.uniform(0.15, 0.55) * fs)
        a, b = max(0, c - half), min(n, c + half)
        if rng.random() < 0.6:
            red[a:b] = np.clip(red[a:b] + rng.uniform(400, 900), None, np.max(red) + 50)
        else:
            ir[a:b] = np.clip(ir[a:b] - rng.uniform(300, 700), np.min(ir) - 50, None)

    # 4) Brief pulse-amplitude dropouts (perfusion) — morphologically different per channel
    for _ in range(max(2, int(n / fs / 40.0))):
        c = int(rng.integers(int(fs), max(int(fs) + 1, n - int(fs))))
        half = int(rng.uniform(0.8, 2.2) * fs)
        a, b = max(0, c - half), min(n, c + half)
        w = np.hanning(max(2, b - a))
        red_dc = float(np.median(red[a:b]))
        ir_dc = float(np.median(ir[a:b]))
        red[a:b] = red_dc + (red[a:b] - red_dc) * (1.0 - 0.65 * w)
        ir[a:b] = ir_dc + (ir[a:b] - ir_dc) * (1.0 - 0.35 * w)

    # 5) Occasional single-sample spikes (EMI / LED switching)
    n_spikes = max(8, int(n / fs * 0.4))
    for _ in range(n_spikes):
        i = int(rng.integers(0, n))
        if rng.random() < 0.65:
            red[i] += rng.choice([-1.0, 1.0]) * rng.uniform(200, 800)
        else:
            ir[i] += rng.choice([-1.0, 1.0]) * rng.uniform(150, 500)


def _instant_hr_series(n: int, fs: float, r_peaks: np.ndarray, fallback: float) -> np.ndarray:
    hr = np.full(n, fallback, dtype=np.float64)
    peaks = np.asarray(r_peaks, dtype=int)
    peaks = peaks[(peaks >= 0) & (peaks < n)]
    if len(peaks) < 2:
        return hr
    for i in range(len(peaks) - 1):
        a, b = int(peaks[i]), int(peaks[i + 1])
        rr = (b - a) / fs
        if rr > 1e-6:
            bpm = 60.0 / rr
            if 50 <= bpm <= 230:
                hr[a:b] = bpm
    if peaks[-1] > 0:
        hr[peaks[-1] :] = hr[peaks[-1] - 1]
    return hr


def synthesize_from_real_bio(cfg: Optional[RealBioDemoConfig] = None) -> BeltRecording:
    """Real adult ECG/PPG/RSP, sped up toward neonatal demo rates."""
    import neurokit2 as nk

    cfg = cfg or RealBioDemoConfig()
    fs = float(cfg.sampling_rate)
    n = int(round(cfg.duration_s * fs))
    seed = int(cfg.seed)
    rng = np.random.default_rng(seed)

    ecg0, ppg0, rsp0 = _load_real_bio(fs)
    adult_hr = _measure_hr(ecg0, fs)
    if not np.isfinite(adult_hr) or adult_hr < 40:
        adult_hr = 75.0

    speed = float(np.clip(cfg.target_hr_bpm / adult_hr, cfg.min_speed, cfg.max_speed))

    ecg = _speed_up(ecg0, speed)
    ppg = _speed_up(ppg0, speed)
    rsp = _speed_up(rsp0, speed)

    # Tile to requested duration
    ecg = _tile(ecg, n)
    ppg = _tile(ppg, n)
    rsp = _tile(rsp, n)

    # Soft seams at tile boundaries (crossfade 0.25 s)
    seam = max(4, int(0.25 * fs))
    # After tiling, optional light high-pass-ish detrend is unnecessary — keep morphology

    # Scale ECG to belt-like ADC range while preserving shape
    ecg_adc = _normalize(ecg) * 22000.0

    rsp_n = _normalize(rsp)
    resp0 = 20.0 + 2.2 * rsp_n + rng.normal(0, 0.01, n)
    lag = max(1, int(0.06 * fs))
    resp1 = 23.2 + 1.4 * np.roll(rsp_n, lag) + rng.normal(0, 0.01, n)

    device_spo2 = _make_spo2_series(n, fs, cfg.spo2_pct, seed + 21)
    temp = _make_temp_series(n, fs, cfg.temp_f, seed + 22)

    red, ir = _make_red_ir_from_ppg(ppg, rsp, device_spo2, fs, seed + 4)
    motion_env = _motion_burst_envelope(n, fs, seed + 11)
    ax, ay, az, gx, gy, gz = _make_imu_with_breathing(rsp, fs, seed, motion_env)

    _inject_ppg_and_motion_artifacts(
        ecg=ecg_adc,
        red=red,
        ir=ir,
        resp0=resp0,
        resp1=resp1,
        motion_env=motion_env,
        fs=fs,
        seed=seed + 33,
    )

    try:
        _, info = nk.ecg_peaks(ecg_adc, sampling_rate=fs)
        r_peaks = np.asarray(info.get("ECG_R_Peaks", []), dtype=int)
    except Exception:
        r_peaks = np.array([], dtype=int)

    measured_hr = _measure_hr(ecg_adc, fs)
    fallback_hr = measured_hr if np.isfinite(measured_hr) else cfg.target_hr_bpm
    device_hr = _instant_hr_series(n, fs, r_peaks, fallback_hr)
    win = max(3, int(fs))
    device_hr = np.convolve(device_hr, np.ones(win) / win, mode="same")

    return BeltRecording(
        path=Path(
            f"REALBIO_x{speed:.2f}_HR{int(round(fallback_hr))}.csv"
        ),
        sampling_rate=fs,
        n_samples=n,
        duration_s=n / fs,
        ecg=ecg_adc,
        resp0=resp0,
        resp1=resp1,
        ir=_fit_len(ir, n),
        red=_fit_len(red, n),
        temp=temp,
        device_hr=device_hr,
        device_spo2=device_spo2,
        acc_x=_fit_len(ax, n),
        acc_y=_fit_len(ay, n),
        acc_z=_fit_len(az, n),
        gyro_x=_fit_len(gx, n),
        gyro_y=_fit_len(gy, n),
        gyro_z=_fit_len(gz, n),
    )


def recording_to_dataframe(rec: BeltRecording) -> pd.DataFrame:
    n = rec.n_samples
    t = np.arange(n, dtype=np.float64) / rec.sampling_rate
    return pd.DataFrame(
        {
            "PC_Time": t,
            "Seq": np.arange(n, dtype=np.float64),
            "Tx_ms": np.arange(n, dtype=np.float64) * (1000.0 / rec.sampling_rate),
            "Rx_ms": np.arange(n, dtype=np.float64) * (1000.0 / rec.sampling_rate),
            "Latency": np.zeros(n),
            "InterArrival": np.full(n, 1000.0 / rec.sampling_rate),
            "ECG": rec.ecg,
            "Resp0": rec.resp0,
            "Resp1": rec.resp1,
            "SpO2": rec.device_spo2,
            "HR": rec.device_hr,
            "IR": rec.ir,
            "Red": rec.red,
            "Temp": rec.temp,
            "AccX": rec.acc_x,
            "AccY": rec.acc_y,
            "AccZ": rec.acc_z,
            "GyroX": rec.gyro_x,
            "GyroY": rec.gyro_y,
            "GyroZ": rec.gyro_z,
            "MagX": np.zeros(n),
            "MagY": np.zeros(n),
            "MagZ": np.zeros(n),
        }
    )


def generate_neonate_demo_csv(
    out_path: Optional[str | Path] = None,
    cfg: Optional[RealBioDemoConfig] = None,
) -> Path:
    """
    Write demo CSV from real bio signals (sped up).

    Kept name for UI/CLI compatibility with earlier ``--neonate`` / Generate button.
    """
    cfg = cfg or RealBioDemoConfig()
    rec = synthesize_from_real_bio(cfg)
    out = Path(out_path) if out_path else (DEFAULT_SAMPLE_DIR / "NEONATE_SYNTH_DEMO.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    recording_to_dataframe(rec).to_csv(out, index=False)
    return out


# Back-compat alias
NeonateSynthConfig = RealBioDemoConfig
synthesize_neonate_recording = synthesize_from_real_bio


__all__ = [
    "RealBioDemoConfig",
    "NeonateSynthConfig",
    "synthesize_from_real_bio",
    "synthesize_neonate_recording",
    "generate_neonate_demo_csv",
    "recording_to_dataframe",
]
