"""Reusable medical-monitor widgets for the NeoTex Signal View."""

from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from neotex.constants import THEME


class MetricCard(QtWidgets.QFrame):
    """Large vital-sign readout used in the left rail."""

    def __init__(self, key: str, unit: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self._color = color
        self.setStyleSheet(
            f"""
            QFrame#MetricCard {{
                background-color: {THEME['metric_bg']};
                border: 1px solid {THEME['border']};
                border-left: 3px solid {color};
                border-radius: 10px;
            }}
            """
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        self.key_label = QtWidgets.QLabel(key)
        self.key_label.setStyleSheet(
            f"color: {THEME['text_dim']}; font-family: 'Bahnschrift'; "
            f"font-size: 13px; letter-spacing: 2px; font-weight: 600;"
        )

        self.value_label = QtWidgets.QLabel("--")
        self.value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.value_label.setStyleSheet(
            f"color: {color}; font-family: 'Cascadia Mono', 'Consolas', monospace; "
            f"font-size: 42px; font-weight: 700;"
        )

        self.unit_label = QtWidgets.QLabel(unit)
        self.unit_label.setStyleSheet(
            f"color: {THEME['text_dim']}; font-family: 'Bahnschrift'; font-size: 12px;"
        )

        layout.addWidget(self.key_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.unit_label)
        layout.addStretch(1)

    def set_value(self, value) -> None:
        if value is None:
            self.value_label.setText("--")
        elif isinstance(value, float):
            self.value_label.setText(f"{value:.1f}" if value < 1000 else f"{value:.0f}")
        else:
            self.value_label.setText(str(value))


class WavePlot(QtWidgets.QWidget):
    """Labeled scrolling waveform strip with smooth Y autoscaling."""

    def __init__(self, title: str, color: str, capacity: int, parent=None):
        super().__init__(parent)
        self.capacity = capacity
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.title = QtWidgets.QLabel(title)
        self.title.setFixedWidth(56)
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        self.title.setStyleSheet(
            f"color: {color}; font-family: 'Bahnschrift'; font-size: 14px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        layout.addWidget(self.title)

        self.plot = pg.PlotWidget()
        self.plot.setBackground(THEME["plot_bg"])
        self.plot.showGrid(x=False, y=False)
        self.plot.hideAxis("bottom")
        self.plot.getAxis("left").setTextPen(THEME["text_dim"])
        self.plot.getAxis("left").setPen(THEME["border"])
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        self.plot.enableAutoRange(x=False, y=False)
        self.plot.setXRange(0, capacity - 1, padding=0)
        self.plot.setYRange(-1, 1, padding=0.05)
        # Clip to reduce visual jumpiness from outliers
        self.curve = self.plot.plot(
            pen=pg.mkPen(color=color, width=1.6),
            clipToView=True,
            skipFiniteCheck=True,
        )
        layout.addWidget(self.plot, stretch=1)

        self._data = [float("nan")] * capacity
        self._idx = 0
        self._y_lo: float | None = None
        self._y_hi: float | None = None

    def smooth_set_yrange(self, lo: float, hi: float, alpha: float = 0.12) -> None:
        """EMA + hysteresis so the strip doesn't constantly rezoom."""
        if hi <= lo:
            hi = lo + 1.0
        span = hi - lo
        pad = 0.12 * span
        tgt_lo, tgt_hi = lo - pad, hi + pad

        if self._y_lo is None or self._y_hi is None:
            self._y_lo, self._y_hi = tgt_lo, tgt_hi
            self.plot.setYRange(self._y_lo, self._y_hi, padding=0)
            return

        # EMA toward target
        self._y_lo = (1 - alpha) * self._y_lo + alpha * tgt_lo
        self._y_hi = (1 - alpha) * self._y_hi + alpha * tgt_hi

        # Only apply if range moved enough (hysteresis)
        cur_span = max(self._y_hi - self._y_lo, 1e-9)
        mid = 0.5 * (self._y_lo + self._y_hi)
        tgt_mid = 0.5 * (tgt_lo + tgt_hi)
        mid_shift = abs(mid - tgt_mid) / cur_span
        span_shift = abs((tgt_hi - tgt_lo) - cur_span) / cur_span
        if mid_shift > 0.04 or span_shift > 0.08:
            self.plot.setYRange(self._y_lo, self._y_hi, padding=0)

    def push(self, values) -> None:
        for v in values:
            self._data[self._idx] = float(v)
            self._idx = (self._idx + 1) % self.capacity

    def clear(self) -> None:
        self._data = [float("nan")] * self.capacity
        self._idx = 0
        self._y_lo = None
        self._y_hi = None
        self.curve.setData([])


class HamburgerButton(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 42)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QToolButton {{
                background-color: {THEME['surface']};
                border: 1px solid {THEME['border']};
                border-radius: 8px;
            }}
            QToolButton:hover {{
                border-color: {THEME['accent']};
            }}
            """
        )
        self.setIcon(self._make_icon())
        self.setIconSize(QtCore.QSize(22, 22))

    def _make_icon(self) -> QtGui.QIcon:
        pix = QtGui.QPixmap(22, 22)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor(THEME["text"]))
        pen.setWidth(2)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        for y in (6, 11, 16):
            p.drawLine(4, y, 18, y)
        p.end()
        return QtGui.QIcon(pix)


class SetupDrawer(QtWidgets.QFrame):
    """Slide-over setup panel (file select, stream picks, per-channel prep, API)."""

    file_chosen = QtCore.pyqtSignal(str)
    generate_neonate_requested = QtCore.pyqtSignal()
    restart_requested = QtCore.pyqtSignal()
    start_requested = QtCore.pyqtSignal()
    pause_toggled = QtCore.pyqtSignal(bool)
    streams_changed = QtCore.pyqtSignal(dict)
    prep_changed = QtCore.pyqtSignal(dict)
    rr_source_changed = QtCore.pyqtSignal(str)

    STREAM_KEYS = ("ecg", "ppg_red", "ppg_ir", "resp0", "resp1")

    def __init__(self, parent=None):
        super().__init__(parent)
        from neotex.processing.filters import (
            ECG_PREP_MODES,
            PPG_PREP_MODES,
            RSP_PREP_MODES,
        )

        self.setObjectName("SetupDrawer")
        self.setFixedWidth(360)
        self.setMinimumWidth(320)
        self.setStyleSheet(
            f"""
            QFrame#SetupDrawer {{
                background-color: {THEME['surface']};
                border-right: 1px solid {THEME['border']};
            }}
            QLabel {{ color: {THEME['text']}; font-family: 'Bahnschrift'; }}
            QPushButton {{
                background-color: {THEME['panel']};
                color: {THEME['text']};
                border: 1px solid {THEME['border']};
                border-radius: 8px;
                padding: 10px 12px;
                font-family: 'Bahnschrift';
                font-size: 13px;
            }}
            QPushButton:hover {{ border-color: {THEME['accent']}; }}
            QPushButton#PrimaryBtn {{
                background-color: {THEME['accent_dim']};
                border-color: {THEME['accent']};
                color: {THEME['text']};
                font-weight: 700;
            }}
            QLineEdit, QComboBox {{
                background-color: {THEME['bg']};
                color: {THEME['text']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 6px 8px;
                font-family: 'Cascadia Mono', Consolas, monospace;
                font-size: 11px;
            }}
            QCheckBox {{
                color: {THEME['text']};
                font-family: 'Bahnschrift';
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background: {THEME['bg']};
            }}
            QCheckBox::indicator:checked {{
                background: {THEME['accent']};
                border-color: {THEME['accent']};
            }}
            QScrollArea {{ border: none; background: transparent; }}
            """
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QtWidgets.QWidget()
        scroll.setWidget(content)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("SETUP")
        title.setStyleSheet(
            f"color: {THEME['accent']}; letter-spacing: 3px; font-size: 14px; font-weight: 700;"
        )
        layout.addWidget(title)

        hint = QtWidgets.QLabel(
            "Playback looks like a live USB COM stream.\nSelect a belt CSV to begin."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 12px;")
        layout.addWidget(hint)

        self.file_edit = QtWidgets.QLineEdit()
        self.file_edit.setPlaceholderText("No file selected…")
        self.file_edit.setReadOnly(True)
        layout.addWidget(self.file_edit)

        browse = QtWidgets.QPushButton("Select recording…")
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)

        synth_btn = QtWidgets.QPushButton("Generate demo (real bio, sped-up)")
        synth_btn.setToolTip(
            "Uses NeuroKit real adult ECG/PPG/RSP (bio_resting_5min_100hz), "
            "time-compressed toward neonatal rates, packed as a belt CSV."
        )
        synth_btn.clicked.connect(self.generate_neonate_requested.emit)
        layout.addWidget(synth_btn)

        self.start_btn = QtWidgets.QPushButton("Start livestream")
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.clicked.connect(self.start_requested.emit)
        layout.addWidget(self.start_btn)

        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(self._on_pause)
        layout.addWidget(self.pause_btn)

        restart = QtWidgets.QPushButton("Restart playback")
        restart.clicked.connect(self.restart_requested.emit)
        layout.addWidget(restart)

        # ---- Streams + per-channel prep ----
        streams_title = QtWidgets.QLabel("SIGNAL STREAMS + PREPROCESS")
        streams_title.setStyleSheet(
            f"color: {THEME['text_dim']}; letter-spacing: 2px; font-size: 11px;"
        )
        layout.addWidget(streams_title)

        streams_hint = QtWidgets.QLabel(
            "Enable a channel, then pick its display preprocess."
        )
        streams_hint.setWordWrap(True)
        streams_hint.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;")
        layout.addWidget(streams_hint)

        self.stream_checks: dict[str, QtWidgets.QCheckBox] = {}
        self.prep_combos: dict[str, QtWidgets.QComboBox] = {}

        labels = {
            "ecg": "ECG",
            "ppg_red": "PPG · Red",
            "ppg_ir": "PPG · IR",
            "resp0": "Resp (capacitive)",
            "resp1": "Resp · Ch1 (optional)",
        }
        mode_sets = {
            "ecg": ECG_PREP_MODES,
            "ppg_red": PPG_PREP_MODES,
            "ppg_ir": PPG_PREP_MODES,
            "resp0": RSP_PREP_MODES,
            "resp1": RSP_PREP_MODES,
        }
        default_prep = {
            "ecg": "raw",
            "ppg_red": "ac_invert",
            "ppg_ir": "ac_invert",
            "resp0": "raw",
            "resp1": "raw",
        }
        defaults_on = {
            "ecg": True,
            "ppg_red": True,
            "ppg_ir": True,
            "resp0": True,
            "resp1": False,  # optional second cap channel
        }

        for key in self.STREAM_KEYS:
            row = QtWidgets.QVBoxLayout()
            row.setSpacing(4)

            cb = QtWidgets.QCheckBox(labels[key])
            cb.setChecked(defaults_on[key])
            cb.toggled.connect(self._emit_streams)
            self.stream_checks[key] = cb
            row.addWidget(cb)

            combo = QtWidgets.QComboBox()
            for mode_id, mode_label in mode_sets[key]:
                combo.addItem(mode_label, mode_id)
            # select default
            idx = combo.findData(default_prep[key])
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(self._emit_prep)
            self.prep_combos[key] = combo
            row.addWidget(combo)

            layout.addLayout(row)

        rr_row = QtWidgets.QHBoxLayout()
        rr_lbl = QtWidgets.QLabel("RR source")
        rr_lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 12px;")
        rr_row.addWidget(rr_lbl)
        self.rr_combo = QtWidgets.QComboBox()
        self.rr_combo.addItem("Auto (best Cap)", "auto")
        self.rr_combo.addItem("Resp (capacitive)", "resp0")
        self.rr_combo.addItem("Resp Ch1 (capacitive)", "resp1")
        self.rr_combo.currentIndexChanged.connect(self._emit_rr_source)
        rr_row.addWidget(self.rr_combo, stretch=1)
        layout.addLayout(rr_row)

        api_title = QtWidgets.QLabel("FASTAPI")
        api_title.setStyleSheet(
            f"color: {THEME['text_dim']}; letter-spacing: 2px; font-size: 11px;"
        )
        layout.addWidget(api_title)

        self.api_label = QtWidgets.QLabel("—")
        self.api_label.setWordWrap(True)
        self.api_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.api_label.setStyleSheet(
            f"color: {THEME['spo2']}; font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px;"
        )
        layout.addWidget(self.api_label)

        self.status_label = QtWidgets.QLabel("Idle")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;")
        layout.addWidget(self.status_label)

        layout.addStretch(1)

    def stream_selection(self) -> dict[str, bool]:
        return {k: cb.isChecked() for k, cb in self.stream_checks.items()}

    def prep_selection(self) -> dict[str, str]:
        return {k: str(combo.currentData()) for k, combo in self.prep_combos.items()}

    def rr_source(self) -> str:
        return str(self.rr_combo.currentData())

    def _emit_streams(self, *_args) -> None:
        self.streams_changed.emit(self.stream_selection())

    def _emit_prep(self, *_args) -> None:
        self.prep_changed.emit(self.prep_selection())

    def _emit_rr_source(self, *_args) -> None:
        self.rr_source_changed.emit(self.rr_source())

    def _browse(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select NeoTex belt recording",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self.file_edit.setText(path)
            self.file_chosen.emit(path)

    def _on_pause(self, checked: bool) -> None:
        self.pause_btn.setText("Resume" if checked else "Pause")
        self.pause_toggled.emit(checked)

    def set_api_url(self, url: str) -> None:
        self.api_label.setText(
            f"{url}/vitals/latest\n{url}/vitals/history\n{url}/health"
        )

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)