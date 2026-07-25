"""Load and normalize NeoTex baby-belt CSV recordings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from neotex.constants import SAMPLING_RATE_HZ, SIGNAL_COLUMNS


@dataclass(frozen=True)
class BeltRecording:
    path: Path
    sampling_rate: float
    n_samples: int
    duration_s: float
    # Contiguous float64 arrays for playback
    ecg: np.ndarray
    resp0: np.ndarray
    resp1: np.ndarray
    ir: np.ndarray
    red: np.ndarray
    temp: np.ndarray
    device_hr: np.ndarray
    device_spo2: np.ndarray
    # IMU (N,) each — zeros if missing
    acc_x: np.ndarray
    acc_y: np.ndarray
    acc_z: np.ndarray
    gyro_x: np.ndarray
    gyro_y: np.ndarray
    gyro_z: np.ndarray

    @property
    def resp(self) -> np.ndarray:
        """Best capacitive channel for metrics (higher variance wins)."""
        if np.nanstd(self.resp1) >= np.nanstd(self.resp0):
            return self.resp1
        return self.resp0

    @property
    def acc(self) -> np.ndarray:
        return np.column_stack((self.acc_x, self.acc_y, self.acc_z))

    @property
    def gyro(self) -> np.ndarray:
        return np.column_stack((self.gyro_x, self.gyro_y, self.gyro_z))


def _col_or_zeros(df: pd.DataFrame, name: str, n: int) -> np.ndarray:
    if name in df.columns:
        return df[name].to_numpy(dtype=np.float64)
    return np.zeros(n, dtype=np.float64)


def _load_resp_pair(df: pd.DataFrame, n: int) -> tuple[np.ndarray, np.ndarray]:
    if "Resp0" in df.columns:
        r0 = df["Resp0"].to_numpy(dtype=np.float64)
    else:
        r0 = np.full(n, np.nan)
    if "Resp1" in df.columns:
        r1 = df["Resp1"].to_numpy(dtype=np.float64)
    else:
        r1 = np.full(n, np.nan)
    if np.all(~np.isfinite(r0)) and np.all(~np.isfinite(r1)):
        raise ValueError("CSV missing Resp0/Resp1 columns")
    if np.all(~np.isfinite(r0)):
        r0 = r1.copy()
    if np.all(~np.isfinite(r1)):
        r1 = r0.copy()
    return r0, r1


def estimate_sampling_rate(df: pd.DataFrame) -> float:
    if "PC_Time" in df.columns and len(df) > 10:
        dt = np.diff(df["PC_Time"].to_numpy(dtype=np.float64))
        dt = dt[np.isfinite(dt) & (dt > 1e-4)]
        if len(dt):
            med = float(np.median(dt))
            if med > 0:
                return float(round(1.0 / med))
    if "InterArrival" in df.columns:
        ia = df["InterArrival"].to_numpy(dtype=np.float64)
        ia = ia[np.isfinite(ia) & (ia > 0)]
        if len(ia):
            med_ms = float(np.median(ia))
            if med_ms > 0:
                return float(round(1000.0 / med_ms))
    return float(SAMPLING_RATE_HZ)


def load_belt_csv(path: str | Path, sampling_rate: Optional[float] = None) -> BeltRecording:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path)
    missing = [c for c in ("ECG", "IR", "Red", "Temp") if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    fs = float(sampling_rate) if sampling_rate else estimate_sampling_rate(df)
    n = len(df)
    duration = n / fs if fs > 0 else 0.0
    resp0, resp1 = _load_resp_pair(df, n)

    device_hr = (
        df["HR"].to_numpy(dtype=np.float64)
        if "HR" in df.columns
        else np.full(n, np.nan)
    )
    device_spo2 = (
        df["SpO2"].to_numpy(dtype=np.float64)
        if "SpO2" in df.columns
        else np.full(n, np.nan)
    )

    return BeltRecording(
        path=path,
        sampling_rate=fs,
        n_samples=n,
        duration_s=duration,
        ecg=df["ECG"].to_numpy(dtype=np.float64),
        resp0=resp0,
        resp1=resp1,
        ir=df["IR"].to_numpy(dtype=np.float64),
        red=df["Red"].to_numpy(dtype=np.float64),
        temp=df["Temp"].to_numpy(dtype=np.float64),
        device_hr=device_hr,
        device_spo2=device_spo2,
        acc_x=_col_or_zeros(df, "AccX", n),
        acc_y=_col_or_zeros(df, "AccY", n),
        acc_z=_col_or_zeros(df, "AccZ", n),
        gyro_x=_col_or_zeros(df, "GyroX", n),
        gyro_y=_col_or_zeros(df, "GyroY", n),
        gyro_z=_col_or_zeros(df, "GyroZ", n),
    )


def list_sample_files(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    if not directory.exists():
        return []
    return sorted(directory.glob("*.csv"))


__all__ = [
    "BeltRecording",
    "SIGNAL_COLUMNS",
    "estimate_sampling_rate",
    "load_belt_csv",
    "list_sample_files",
]
