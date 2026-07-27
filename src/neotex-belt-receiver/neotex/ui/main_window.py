"""NeoTex Baby Monitor — Signal View main window."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread

from neotex.api import STORE, ApiServerWorker
from neotex.constants import (
    DEFAULT_SAMPLE_DIR,
    PLOT_WINDOW_S,
    SAMPLING_RATE_HZ,
    THEME,
)
from neotex.processing.filters import (
    prepare_ecg_display,
    prepare_ppg_display,
    prepare_rsp_display,
)
from neotex.processing.imu_respiration import StreamingIMURespiration
from neotex.ui.chat_panel import NurseChatPanel
from neotex.ui.widgets import HamburgerButton, MetricCard, SetupDrawer, WavePlot
from neotex.utils.ring_buffer import RingBuffer
from neotex.workers.playback_worker import PlaybackWorker
from neotex.workers.processing_worker import ProcessingWorker


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeoTex: Baby monitor")
        self.setMinimumSize(1280, 780)
        self._fs = float(SAMPLING_RATE_HZ)
        self._plot_n = int(self._fs * PLOT_WINDOW_S)
        self._paused_plots = False
        self._file_path: str | None = None
        self._current_view = "signals"  # or "chat"

        # Plot ring buffers (raw display)
        self._buf_ecg = RingBuffer(self._plot_n)
        self._buf_resp0 = RingBuffer(self._plot_n)
        self._buf_resp1 = RingBuffer(self._plot_n)
        self._buf_resp_imu = RingBuffer(self._plot_n)
        self._buf_ir = RingBuffer(self._plot_n)
        self._buf_red = RingBuffer(self._plot_n)
        self._imu_rsp = StreamingIMURespiration(fs=self._fs)
        self._stream_enabled = {
            "ecg": True,
            "ppg_red": True,
            "ppg_ir": True,
            "resp0": True,
            "resp1": False,
            "resp_imu": False,
        }
        self._prep_modes = {
            "ecg": "raw",
            "ppg_red": "ac_invert",
            "ppg_ir": "ac_invert",
            "resp0": "raw",
            "resp1": "raw",
            "resp_imu": "raw",
        }

        self._build_ui()
        self._build_workers()
        self._wire()

        # Prefer scenario demo, then plain neonate synth, then real belt samples
        default = DEFAULT_SAMPLE_DIR / "NEONATE_SCENARIO_DEMO.csv"
        if not default.exists():
            default = DEFAULT_SAMPLE_DIR / "NEONATE_SYNTH_DEMO.csv"
        if not default.exists():
            default = DEFAULT_SAMPLE_DIR / "BABY_BELT_011030062_1_Male_1st.csv"
        if not default.exists():
            default = DEFAULT_SAMPLE_DIR / "P_1_Baby-Belt_1_Male_1st.csv"
        if default.exists():
            self._on_file_chosen(str(default))

        self._api.start()
        self.drawer.set_api_url(self._api.base_url)
        STORE.set_status(streaming=False, file=self._file_path)

        self._plot_timer = QtCore.QTimer(self)
        self._plot_timer.setInterval(33)
        self._plot_timer.timeout.connect(self._redraw_plots)
        self._plot_timer.start()

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget#Root {{
                background-color: {THEME['bg']};
                color: {THEME['text']};
            }}
            QLabel {{ color: {THEME['text']}; }}
            """
        )

        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QtWidgets.QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.drawer = SetupDrawer()
        self.drawer.setVisible(False)
        outer.addWidget(self.drawer)

        main = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)
        outer.addWidget(main, stretch=1)

        # Header
        header = QtWidgets.QHBoxLayout()
        self.menu_btn = HamburgerButton()
        self.menu_btn.clicked.connect(self._toggle_drawer)
        header.addWidget(self.menu_btn)

        self.title_label = QtWidgets.QLabel("NeoTex: Baby monitor (Signal view)")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setStyleSheet(
            f"font-family: 'Bahnschrift'; font-size: 20px; font-weight: 600; "
            f"letter-spacing: 0.5px; color: {THEME['text']};"
        )
        header.addWidget(self.title_label, stretch=1)

        self.ask_btn = QtWidgets.QPushButton("Ask nurse")
        self.ask_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.ask_btn.setStyleSheet(
            f"""
            QPushButton {{
                color: {THEME['accent']};
                background: {THEME['surface']};
                border: 1px solid {THEME['border']};
                border-radius: 12px;
                padding: 6px 12px;
                font-family: 'Bahnschrift';
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ border-color: {THEME['accent']}; }}
            """
        )
        self.ask_btn.setToolTip("Open Nurse chat (live vitals stay on the left)")
        self.ask_btn.clicked.connect(self._show_chat_view)
        header.addWidget(self.ask_btn)

        self.live_pill = QtWidgets.QLabel("● STANDBY")
        self.live_pill.setStyleSheet(
            f"color: {THEME['text_dim']}; font-family: 'Bahnschrift'; "
            f"font-size: 12px; letter-spacing: 1px; padding: 6px 10px; "
            f"background: {THEME['surface']}; border: 1px solid {THEME['border']}; "
            f"border-radius: 12px;"
        )
        header.addWidget(self.live_pill)
        main_layout.addLayout(header)

        # Body: metrics (always) | stacked main pane (signals | chat)
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)

        metrics_col = QtWidgets.QVBoxLayout()
        metrics_col.setSpacing(10)
        self.card_hr = MetricCard("HR", "bpm", THEME["hr"], icon_kind="hr")
        self.card_rr = MetricCard("RR", "/min", THEME["rr"], icon_kind="rr")
        self.card_o2 = MetricCard("O₂", "% SpO₂", THEME["spo2"], icon_kind="o2")
        self.card_tmp = MetricCard("TMP", "°F", THEME["temp"], icon_kind="tmp")
        for card in (self.card_hr, self.card_rr, self.card_o2, self.card_tmp):
            metrics_col.addWidget(card, stretch=1)
        body.addLayout(metrics_col, stretch=1)

        self.main_stack = QtWidgets.QStackedWidget()
        self.main_stack.setStyleSheet("QStackedWidget { background: transparent; }")

        # --- Signals page ---
        streams = QtWidgets.QFrame()
        streams.setObjectName("Streams")
        streams.setStyleSheet(
            f"""
            QFrame#Streams {{
                background-color: {THEME['surface']};
                border: 1px solid {THEME['border']};
                border-radius: 14px;
            }}
            """
        )
        streams_layout = QtWidgets.QVBoxLayout(streams)
        streams_layout.setContentsMargins(14, 12, 14, 12)
        streams_layout.setSpacing(8)

        stream_header = QtWidgets.QHBoxLayout()
        streams_title = QtWidgets.QLabel("Signal Streams")
        streams_title.setStyleSheet(
            f"font-family: 'Bahnschrift'; font-size: 14px; font-weight: 700; "
            f"color: {THEME['text_dim']}; letter-spacing: 1px;"
        )
        stream_header.addWidget(streams_title)
        stream_header.addStretch(1)
        self.ts_label = QtWidgets.QLabel("unix —")
        self.ts_label.setStyleSheet(
            f"color: {THEME['text_dim']}; font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px;"
        )
        stream_header.addWidget(self.ts_label)
        streams_layout.addLayout(stream_header)

        self.plot_ecg = WavePlot("ECG", THEME["ecg"], self._plot_n)
        self.plot_ppg_red = WavePlot("RED", THEME["ppg_red"], self._plot_n)
        self.plot_ppg_ir = WavePlot("IR", THEME["ppg_ir"], self._plot_n)
        self.plot_rsp0 = WavePlot("Resp", THEME["rsp0"], self._plot_n)
        self.plot_rsp1 = WavePlot("R1", THEME["rsp1"], self._plot_n)

        self._plot_map = {
            "ecg": self.plot_ecg,
            "ppg_red": self.plot_ppg_red,
            "ppg_ir": self.plot_ppg_ir,
            "resp0": self.plot_rsp0,
            "resp1": self.plot_rsp1,
        }
        for plot in self._plot_map.values():
            streams_layout.addWidget(plot, stretch=1)

        # --- Chat page ---
        self.chat = NurseChatPanel()
        self.chat.message_submitted.connect(self._on_chat_message)
        self.chat.back_to_signals_requested.connect(self._show_signals_view)

        self._page_signals = 0
        self._page_chat = 1
        self.main_stack.addWidget(streams)
        self.main_stack.addWidget(self.chat)

        body.addWidget(self.main_stack, stretch=5)
        main_layout.addLayout(body, stretch=1)

        self._set_view("signals")

    def _build_workers(self) -> None:
        self._playback: PlaybackWorker | None = None

        self._proc = ProcessingWorker(fs=self._fs)
        self._proc_thread = QThread(self)
        self._proc.moveToThread(self._proc_thread)
        self._proc_thread.started.connect(self._proc.run)

        self._api = ApiServerWorker()

    def _wire(self) -> None:
        self.drawer.file_chosen.connect(self._on_file_chosen)
        self.drawer.generate_neonate_requested.connect(self._generate_neonate_demo)
        self.drawer.start_requested.connect(self._start_stream)
        self.drawer.restart_requested.connect(self._restart)
        self.drawer.pause_toggled.connect(self._toggle_pause)
        self.drawer.streams_changed.connect(self._on_streams_changed)
        self.drawer.prep_changed.connect(self._on_prep_changed)
        self.drawer.rr_source_changed.connect(self._on_rr_source_changed)
        self.drawer.view_signals_requested.connect(self._show_signals_view)
        self.drawer.view_chat_requested.connect(self._show_chat_view)

        self._proc.vitals_result.connect(self._on_vitals)
        self._proc.status.connect(self._on_status)
        self._api.status.connect(self._on_status)

        # Apply defaults from drawer
        self._on_streams_changed(self.drawer.stream_selection())
        self._on_prep_changed(self.drawer.prep_selection())
        self._on_rr_source_changed(self.drawer.rr_source())

    def _ensure_playback(self) -> PlaybackWorker:
        """QThread instances are single-shot — recreate after stop."""
        if self._playback is not None and self._playback.isRunning():
            return self._playback

        if self._playback is not None:
            self._playback.stop()
            self._playback.wait(1000)

        self._playback = PlaybackWorker()
        self._playback.samples_chunk.connect(self._on_chunk)
        self._playback.status.connect(self._on_status)
        self._playback.progress.connect(self._on_progress)
        if self._file_path:
            self._playback.load_file(self._file_path)
        return self._playback

    # ------------------------------------------------------------------ #
    #  Control
    # ------------------------------------------------------------------ #

    def _toggle_drawer(self) -> None:
        self.drawer.setVisible(not self.drawer.isVisible())

    def _set_view(self, view: str) -> None:
        view = "chat" if view == "chat" else "signals"
        self._current_view = view
        if view == "chat":
            self.main_stack.setCurrentIndex(self._page_chat)
            self.title_label.setText("NeoTex: Baby monitor (Nurse chat)")
            self.ask_btn.setVisible(False)
            self.drawer.view_chat_btn.setObjectName("PrimaryBtn")
            self.drawer.view_signals_btn.setObjectName("")
            self.chat.focus_input()
        else:
            self.main_stack.setCurrentIndex(self._page_signals)
            self.title_label.setText("NeoTex: Baby monitor (Signal view)")
            self.ask_btn.setVisible(True)
            self.drawer.view_signals_btn.setObjectName("PrimaryBtn")
            self.drawer.view_chat_btn.setObjectName("")
        # Refresh button styles after objectName change
        for btn in (self.drawer.view_signals_btn, self.drawer.view_chat_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _show_signals_view(self) -> None:
        self._set_view("signals")

    def _show_chat_view(self) -> None:
        self._set_view("chat")

    def _generate_neonate_demo(self) -> None:
        """Build apnea/desat scenario demo CSV and load it."""
        try:
            from neotex.utils.demo_scenario import (
                ScenarioConfig,
                generate_scenario_demo_csv,
            )

            self.drawer.set_status("Building sample recording…")
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            QtWidgets.QApplication.processEvents()
            out = generate_scenario_demo_csv(
                DEFAULT_SAMPLE_DIR / "NEONATE_SCENARIO_DEMO.csv",
                ScenarioConfig(duration_s=180.0, target_hr_bpm=140.0, seed=42),
            )
            self._on_file_chosen(str(out))
            self.drawer.set_status(f"Sample ready · {out.name}")
            idx = self.drawer.rr_combo.findData("resp0")
            if idx >= 0:
                self.drawer.rr_combo.setCurrentIndex(idx)
            for key, mode in (
                ("ppg_red", "ac_invert"),
                ("ppg_ir", "ac_invert"),
                ("ecg", "raw"),
                ("resp0", "raw"),
            ):
                combo = self.drawer.prep_combos.get(key)
                if combo is None:
                    continue
                i = combo.findData(mode)
                if i >= 0:
                    combo.setCurrentIndex(i)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self, "Generate failed", str(exc)
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _on_file_chosen(self, path: str) -> None:
        self._file_path = path
        try:
            from neotex.utils.data_loader import load_belt_csv

            rec = load_belt_csv(path)
            self._fs = rec.sampling_rate
            self._proc.set_sampling_rate(self._fs)
            self._proc.set_source_file(Path(path).name)
            self._imu_rsp.set_sampling_rate(self._fs)
            self._imu_rsp.reset()
            self.drawer.file_edit.setText(path)
            self.drawer.set_status(
                f"Ready · {rec.sampling_rate:.0f} Hz · {rec.duration_s:.1f}s"
            )
            STORE.set_status(file=Path(path).name, streaming=False)
            if self._playback is not None and self._playback.isRunning():
                self._restart()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(exc))

    def _start_stream(self) -> None:
        if self._file_path is None:
            QtWidgets.QMessageBox.information(
                self, "Select a file", "Choose a belt CSV from the setup menu first."
            )
            self.drawer.setVisible(True)
            return

        if not self._proc_thread.isRunning():
            self._proc_thread.start()

        pb = self._ensure_playback()
        if pb.isRunning():
            pb.resume()
        else:
            self._proc.clear()
            self._clear_plots()
            pb.start()

        self.drawer.pause_btn.setChecked(False)
        self._set_live(True)
        STORE.set_status(streaming=True, file=Path(self._file_path).name)

    def _restart(self) -> None:
        if self._file_path is None:
            return
        if self._playback is not None:
            self._playback.stop()
            self._playback.wait(1500)
            self._playback = None
        self._proc.clear()
        self._clear_plots()
        if not self._proc_thread.isRunning():
            self._proc_thread.start()
        pb = self._ensure_playback()
        pb.restart()
        pb.start()
        self.drawer.pause_btn.setChecked(False)
        self._set_live(True)
        STORE.set_status(streaming=True, file=Path(self._file_path).name)

    def _toggle_pause(self, paused: bool) -> None:
        if self._playback is None:
            return
        if paused:
            self._playback.pause()
            self._set_live(False, paused=True)
            STORE.set_status(streaming=False)
        else:
            self._playback.resume()
            self._set_live(True)
            STORE.set_status(streaming=True)

    def _set_live(self, live: bool, paused: bool = False) -> None:
        if paused:
            self.live_pill.setText("● PAUSED")
            color = THEME["warning"]
        elif live:
            self.live_pill.setText("● LIVE")
            color = THEME["live"]
        else:
            self.live_pill.setText("● STANDBY")
            color = THEME["text_dim"]
        self.live_pill.setStyleSheet(
            f"color: {color}; font-family: 'Bahnschrift'; font-size: 12px; "
            f"letter-spacing: 1px; padding: 6px 10px; background: {THEME['surface']}; "
            f"border: 1px solid {THEME['border']}; border-radius: 12px;"
        )

    # ------------------------------------------------------------------ #
    #  Data path
    # ------------------------------------------------------------------ #

    def _on_streams_changed(self, enabled: dict) -> None:
        self._stream_enabled = dict(enabled)
        for key, plot in self._plot_map.items():
            plot.setVisible(bool(enabled.get(key, False)))

    def _on_prep_changed(self, modes: dict) -> None:
        self._prep_modes = dict(modes)

    def _on_rr_source_changed(self, source: str) -> None:
        self._proc.set_rr_source(source)

    @QtCore.pyqtSlot(object)
    def _on_chunk(self, chunk: dict) -> None:
        # Per-sample IMU→respiration (causal, stateful)
        acc = chunk.get("acc")
        gyro = chunk.get("gyro")
        if acc is not None and gyro is not None and len(acc):
            resp_imu = self._imu_rsp.process_chunk(acc, gyro)
        else:
            resp_imu = np.zeros(int(chunk.get("n", 0)), dtype=float)

        chunk_with_imu = dict(chunk)
        chunk_with_imu["resp_imu"] = resp_imu
        self._proc.add_chunk(chunk_with_imu)

        if self._paused_plots:
            return
        self._buf_ecg.extend(chunk["ecg"])
        self._buf_resp0.extend(chunk.get("resp0", chunk.get("resp", [])))
        self._buf_resp1.extend(chunk.get("resp1", chunk.get("resp", [])))
        self._buf_resp_imu.extend(resp_imu)
        self._buf_ir.extend(chunk["ir"])
        self._buf_red.extend(chunk["red"])

    @QtCore.pyqtSlot(str)
    def _on_chat_message(self, question: str) -> None:
        from neotex.agent.stream_timing import prepare_streamed_reply

        # Asking always lands on the Nurse chat pane (vitals stay on the left)
        self._show_chat_view()
        self.chat.append_user(question)
        history = STORE.history(limit=60)
        payload = prepare_streamed_reply(question, history, window_s=180.0)
        self.chat.start_streamed_reply(
            title=f"Nurse · {payload['title']}",
            thinking_steps=payload["thinking_steps"],
            answer_text=payload["text"],
        )

    @QtCore.pyqtSlot(object)
    def _on_vitals(self, payload: dict) -> None:
        STORE.publish(payload)
        v = payload.get("vitals", {})
        self.card_hr.set_value(v.get("hr_bpm"))
        self.card_rr.set_value(v.get("rr_bpm"))
        self.card_o2.set_value(v.get("spo2_pct"))
        self.card_tmp.set_value(v.get("temp_f"))
        ts = payload.get("unix_timestamp")
        src = payload.get("rr_source")
        if ts is not None:
            suffix = f" · RR:{src}" if src else ""
            self.ts_label.setText(f"unix {ts:.3f}{suffix}")

    def _on_status(self, text: str) -> None:
        self.drawer.set_status(text)

    def _on_progress(self, frac: float) -> None:
        if not self._file_path:
            return
        name = Path(self._file_path).name
        phase = ""
        if "SCENARIO" in name.upper():
            # Assumes default ScenarioConfig duration 180 s
            t = frac * 180.0
            if t < 30:
                phase = " · phase: baseline"
            elif t < 45:
                phase = " · phase: slowing RR / ↓SpO₂"
            elif t < 75:
                phase = " · phase: nadir"
            elif t < 105:
                phase = " · phase: recovery"
            else:
                phase = " · phase: residual"
        self.drawer.set_status(f"{name} · {frac * 100:.1f}%{phase}")

    def _redraw_plots(self) -> None:
        if self._buf_ecg.count == 0:
            return
        prep = self._prep_modes

        if self._stream_enabled.get("ecg"):
            y = prepare_ecg_display(
                self._buf_ecg.as_array(), self._fs, prep.get("ecg", "bandpass")
            )
            self.plot_ecg.curve.setData(y)
            self._autoscale(self.plot_ecg, arrays=(y,))

        if self._stream_enabled.get("ppg_red"):
            red = prepare_ppg_display(
                self._buf_red.as_array(), self._fs, prep.get("ppg_red", "ac_invert")
            )
            self.plot_ppg_red.curve.setData(red)
            self._autoscale(self.plot_ppg_red, arrays=(red,))

        if self._stream_enabled.get("ppg_ir"):
            ir = prepare_ppg_display(
                self._buf_ir.as_array(), self._fs, prep.get("ppg_ir", "ac_invert")
            )
            self.plot_ppg_ir.curve.setData(ir)
            self._autoscale(self.plot_ppg_ir, arrays=(ir,))

        if self._stream_enabled.get("resp0"):
            r0 = prepare_rsp_display(
                self._buf_resp0.as_array(), self._fs, prep.get("resp0", "dequantize")
            )
            self.plot_rsp0.curve.setData(r0)
            self._autoscale(self.plot_rsp0, arrays=(r0,))

        if self._stream_enabled.get("resp1"):
            r1 = prepare_rsp_display(
                self._buf_resp1.as_array(), self._fs, prep.get("resp1", "dequantize")
            )
            self.plot_rsp1.curve.setData(r1)
            self._autoscale(self.plot_rsp1, arrays=(r1,))

    def _autoscale(self, wave: WavePlot, arrays=None) -> None:
        if arrays is None:
            data = wave.curve.yData
            arrays = (data,) if data is not None else ()
        vals = []
        for arr in arrays:
            if arr is None or len(arr) == 0:
                continue
            a = np.asarray(arr, dtype=float)
            a = a[np.isfinite(a)]
            if a.size:
                vals.append(a)
        if not vals:
            return
        y = np.concatenate(vals)
        if y.size < 16:
            return
        # Percentiles ignore spike outliers that cause jumpy rescales
        lo = float(np.percentile(y, 2))
        hi = float(np.percentile(y, 98))
        if hi - lo < 1e-9:
            hi = lo + 1.0
        wave.smooth_set_yrange(lo, hi)

    def _clear_plots(self) -> None:
        for buf in (
            self._buf_ecg,
            self._buf_resp0,
            self._buf_resp1,
            self._buf_resp_imu,
            self._buf_ir,
            self._buf_red,
        ):
            buf.clear()
        self._imu_rsp.reset()
        for plot in self._plot_map.values():
            plot.clear()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._plot_timer.stop()
        if self._playback is not None:
            self._playback.stop()
            self._playback.wait(1500)
        self._proc.stop()
        self._proc_thread.quit()
        self._proc_thread.wait(2000)
        self._api.stop()
        super().closeEvent(event)