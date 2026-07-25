"""Application-wide constants for the NeoTex Baby Belt monitor."""

from pathlib import Path

# Belt telemetry is nominally 100 Hz (InterArrival ≈ 10 ms).
SAMPLING_RATE_HZ = 100
CHUNK_SAMPLES = 10  # emit 10 samples every 100 ms for lower overhead
PLOT_WINDOW_S = 8
METRICS_INTERVAL_S = 5.0
METRICS_ANALYSIS_WINDOW_S = 20.0  # rolling window used every 5 s

API_HOST = "127.0.0.1"
API_PORT = 8765

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SAMPLE_DIR = REPO_ROOT / "sample-files"

# Clinical monitor palette (deep charcoal + teal — not purple/cream defaults)
THEME = {
    "bg": "#070B14",
    "surface": "#0F172A",
    "surface_alt": "#132038",
    "panel": "#1A2740",
    "border": "#243047",
    "text": "#E8EEF7",
    "text_dim": "#8B9BB4",
    "accent": "#2DD4BF",
    "accent_dim": "#0F766E",
    "danger": "#F87171",
    "warning": "#FBBF24",
    "live": "#34D399",
    "hr": "#F87171",
    "rr": "#38BDF8",
    "spo2": "#2DD4BF",
    "temp": "#FBBF24",
    "ecg": "#4ADE80",
    "ppg_red": "#FB7185",
    "ppg_ir": "#F59E0B",
    "rsp": "#22D3EE",
    "rsp0": "#22D3EE",
    "rsp1": "#A78BFA",
    "rsp_imu": "#F472B6",
    "chat_bg": "#14261F",
    "chat_border": "#1F4D3A",
    "metric_bg": "#121C2E",
    "plot_bg": "#060A12",
    "grid": "#1C2A40",
}

SIGNAL_COLUMNS = ("ECG", "Resp0", "Resp1", "IR", "Red", "Temp", "SpO2", "HR")