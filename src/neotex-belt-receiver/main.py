"""
NeoTex Baby Belt — live demo playback app.

Streams belt CSV recordings at the native sampling rate (looks like a USB COM
livestream), shows ECG / PPG / respiration, computes NeuroKit2 vitals every 5 s,
and publishes JSON over FastAPI.

Usage:
    uv run python main.py
    uv run python main.py --neonate --autoplay
    uv run python main.py --scenario --autoplay
    uv run python main.py --file ../../sample-files/NEONATE_SCENARIO_DEMO.csv --autoplay
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NeoTex Baby Belt Signal View")
    parser.add_argument("--file", type=str, default=None, help="Belt CSV to preload")
    parser.add_argument(
        "--neonate",
        action="store_true",
        help="Generate neonatal scenario demo (30s normal → bradypnea/desat/↓HR)",
    )
    parser.add_argument(
        "--scenario",
        action="store_true",
        help="Same as --neonate (booth apnea/desat scenario)",
    )
    parser.add_argument(
        "--autoplay",
        action="store_true",
        help="Start playback immediately after load",
    )
    args = parser.parse_args(argv)

    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("NeoTex Baby Monitor")
    app.setStyle("Fusion")

    from neotex.constants import DEFAULT_SAMPLE_DIR
    from neotex.ui.main_window import MainWindow

    if args.neonate or args.scenario:
        from neotex.utils.demo_scenario import (
            ScenarioConfig,
            generate_scenario_demo_csv,
        )

        out = generate_scenario_demo_csv(
            DEFAULT_SAMPLE_DIR / "NEONATE_SCENARIO_DEMO.csv",
            ScenarioConfig(duration_s=180.0, target_hr_bpm=140.0),
        )
        args.file = str(out)

    window = MainWindow()
    if args.file:
        window._on_file_chosen(args.file)
    if args.autoplay:
        QTimer.singleShot(400, window._start_stream)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
