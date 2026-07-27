"""
Booth demo scenario: normal vitals, then bradypnea + desaturation + bradycardia.

Timeline (default):
  0–30 s   stable neonatal baseline
  30–45 s  ramp — respiration slows, SpO₂ falls, HR follows down
  45–75 s  nadir hold (slow RR, low SpO₂, lower HR)
  75–105 s partial recovery
  105+ s   near-baseline with mild residual

Implemented by time-warping real-bio waveforms (cardiac vs respiratory scales)
so beat/breath morphology stays real while rates change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from neotex.constants import DEFAULT_SAMPLE_DIR, SAMPLING_RATE_HZ
from neotex.utils.data_loader import BeltRecording
from neotex.utils.neonate_synth import (
    RealBioDemoConfig,
    _fit_len,
    _inject_ppg_and_motion_artifacts,
    _instant_hr_series,
    _load_real_bio,
    _make_imu_with_breathing,
    _make_red_ir_from_ppg,
    _make_temp_series,
    _measure_hr,
    _motion_burst_envelope,
    _normalize,
    _speed_up,
    _tile,
    recording_to_dataframe,
)


@dataclass(frozen=True)
class ScenarioConfig:
    duration_s: float = 180.0
    sampling_rate: float = float(SAMPLING_RATE_HZ)
    target_hr_bpm: float = 140.0
    baseline_spo2: float = 98.0
    nadir_spo2: float = 86.0
    temp_f: float = 98.6
    # Event timing
    normal_s: float = 30.0
    ramp_s: float = 15.0
    hold_s: float = 30.0
    recover_s: float = 30.0
    # Rate scales at nadir (1.0 = baseline neonatal)
    cardio_nadir_scale: float = 0.68   # HR ~140 → ~95
    resp_nadir_scale: float = 0.42     # breathing slows more than HR
    seed: int = 42


def _smoothstep(u: np.ndarray) -> np.ndarray:
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def _event_severity(n: int, fs: float, cfg: ScenarioConfig) -> np.ndarray:
    """
    0 = baseline, 1 = full event nadir.
    Ramps in after normal_s, holds, then recovers toward ~0.15 residual.
    """
    t = np.arange(n, dtype=np.float64) / fs
    sev = np.zeros(n, dtype=np.float64)
    t0 = cfg.normal_s
    t1 = t0 + cfg.ramp_s
    t2 = t1 + cfg.hold_s
    t3 = t2 + cfg.recover_s

    ramp = _smoothstep((t - t0) / max(cfg.ramp_s, 1e-6))
    recover = 1.0 - 0.85 * _smoothstep((t - t2) / max(cfg.recover_s, 1e-6))

    for i in range(n):
        ti = t[i]
        if ti < t0:
            sev[i] = 0.0
        elif ti < t1:
            sev[i] = float(ramp[i])
        elif ti < t2:
            sev[i] = 1.0
        elif ti < t3:
            sev[i] = float(recover[i])
        else:
            sev[i] = 0.15
    return sev


def _rate_scale_series(severity: np.ndarray, nadir: float) -> np.ndarray:
    return 1.0 - (1.0 - float(nadir)) * severity


def _warp_by_rate(x: np.ndarray, rate_scale: np.ndarray) -> np.ndarray:
    """
    Time-warp ``x`` so instantaneous playback rate follows ``rate_scale``.
    rate_scale < 1 stretches the signal → slower HR/RR.
    """
    x = np.asarray(x, dtype=np.float64)
    rate_scale = np.asarray(rate_scale, dtype=np.float64)
    n = len(rate_scale)
    # Need enough source: integral of rate over output length
    src_pos = np.cumsum(np.clip(rate_scale, 0.15, 1.5))
    src_pos = src_pos - src_pos[0]
    max_src = int(np.ceil(src_pos[-1])) + 4
    src = _tile(x, max_src)
    return np.interp(src_pos, np.arange(len(src), dtype=np.float64), src)


def synthesize_scenario_recording(cfg: Optional[ScenarioConfig] = None) -> BeltRecording:
    """Normal 30 s, then slowing respiration + desat with matching HR drop."""
    import neurokit2 as nk

    cfg = cfg or ScenarioConfig()
    fs = float(cfg.sampling_rate)
    n = int(round(cfg.duration_s * fs))
    seed = int(cfg.seed)
    rng = np.random.default_rng(seed)

    ecg0, ppg0, rsp0 = _load_real_bio(fs)
    adult_hr = _measure_hr(ecg0, fs)
    if not np.isfinite(adult_hr) or adult_hr < 40:
        adult_hr = 75.0

    bio_cfg = RealBioDemoConfig(
        duration_s=cfg.duration_s,
        sampling_rate=fs,
        target_hr_bpm=cfg.target_hr_bpm,
        spo2_pct=cfg.baseline_spo2,
        temp_f=cfg.temp_f,
        seed=seed,
    )
    speed = float(
        np.clip(bio_cfg.target_hr_bpm / adult_hr, bio_cfg.min_speed, bio_cfg.max_speed)
    )

    # Baseline neonatal-rate streams (long enough for warping)
    ecg_n = _tile(_speed_up(ecg0, speed), n * 2)
    ppg_n = _tile(_speed_up(ppg0, speed), n * 2)
    rsp_n = _tile(_speed_up(rsp0, speed), n * 2)

    severity = _event_severity(n, fs, cfg)
    cardio_scale = _rate_scale_series(severity, cfg.cardio_nadir_scale)
    resp_scale = _rate_scale_series(severity, cfg.resp_nadir_scale)

    ecg_w = _warp_by_rate(ecg_n, cardio_scale)
    ppg_w = _warp_by_rate(ppg_n, cardio_scale)
    rsp_w = _warp_by_rate(rsp_n, resp_scale)

    ecg_adc = _normalize(ecg_w) * 22000.0
    # During event, slightly lower QRS amplitude (poor perfusion look)
    ecg_adc *= 1.0 - 0.12 * severity

    rsp_norm = _normalize(rsp_w)
    # Shallower breaths as severity rises
    breath_amp = 2.2 * (1.0 - 0.45 * severity)
    resp0 = 20.0 + breath_amp * rsp_norm + rng.normal(0, 0.015, n)
    lag = max(1, int(0.06 * fs))
    resp1 = 23.2 + 0.65 * breath_amp * np.roll(rsp_norm, lag) + rng.normal(0, 0.015, n)

    # SpO2: baseline → nadir with severity (+ tiny grain)
    device_spo2 = cfg.baseline_spo2 - (cfg.baseline_spo2 - cfg.nadir_spo2) * severity
    device_spo2 = device_spo2 + rng.normal(0, 0.2, n)
    device_spo2 = np.clip(device_spo2, 82.0, 100.0)

    temp = _make_temp_series(n, fs, cfg.temp_f, seed + 22)

    red, ir = _make_red_ir_from_ppg(ppg_w, rsp_w, device_spo2, fs, seed + 4)
    # Optical perfusion drop during desat event
    for ch in (red, ir):
        dc = float(np.median(ch))
        ch[:] = dc + (ch - dc) * (1.0 - 0.35 * severity)

    motion_env = _motion_burst_envelope(n, fs, seed + 11)
    # Extra restlessness as SpO2 falls
    motion_env = np.clip(motion_env + 0.35 * severity * _motion_burst_envelope(n, fs, seed + 99), 0, 1)
    ax, ay, az, gx, gy, gz = _make_imu_with_breathing(rsp_w, fs, seed, motion_env)

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
    # Blend toward expected HR trajectory so UI cards move even if peak detect is noisy
    expected_hr = cfg.target_hr_bpm * cardio_scale
    device_hr = 0.65 * device_hr + 0.35 * expected_hr
    win = max(3, int(fs))
    device_hr = np.convolve(device_hr, np.ones(win) / win, mode="same")

    return BeltRecording(
        path=Path("SCENARIO_bradypnea_desat.csv"),
        sampling_rate=fs,
        n_samples=n,
        duration_s=n / fs,
        ecg=_fit_len(ecg_adc, n),
        resp0=_fit_len(resp0, n),
        resp1=_fit_len(resp1, n),
        ir=_fit_len(ir, n),
        red=_fit_len(red, n),
        temp=_fit_len(temp, n),
        device_hr=_fit_len(device_hr, n),
        device_spo2=_fit_len(device_spo2, n),
        acc_x=_fit_len(ax, n),
        acc_y=_fit_len(ay, n),
        acc_z=_fit_len(az, n),
        gyro_x=_fit_len(gx, n),
        gyro_y=_fit_len(gy, n),
        gyro_z=_fit_len(gz, n),
    )


def generate_scenario_demo_csv(
    out_path: Optional[str | Path] = None,
    cfg: Optional[ScenarioConfig] = None,
) -> Path:
    """Write bradypnea/desat scenario CSV for booth playback."""
    cfg = cfg or ScenarioConfig()
    rec = synthesize_scenario_recording(cfg)
    out = Path(out_path) if out_path else (DEFAULT_SAMPLE_DIR / "NEONATE_SCENARIO_DEMO.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    recording_to_dataframe(rec).to_csv(out, index=False)
    return out


__all__ = [
    "ScenarioConfig",
    "synthesize_scenario_recording",
    "generate_scenario_demo_csv",
]
