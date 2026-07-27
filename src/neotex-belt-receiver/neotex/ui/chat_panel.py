"""Nurse-agent chat panel with thinking + streamed replies."""

from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets

from neotex.agent.stream_timing import STREAM_CHARS_PER_SEC, THINK_STEP_MS
from neotex.constants import THEME


class NurseChatPanel(QtWidgets.QFrame):
    """Full-pane chat: history + live thinking/stream + input."""

    message_submitted = QtCore.pyqtSignal(str)
    back_to_signals_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatPanel")
        self._busy = False
        self._think_steps: list[str] = []
        self._think_i = 0
        self._answer_full = ""
        self._answer_i = 0
        self._stream_title = "Nurse"
        self._tick_ms = 40
        self._chars_per_tick = max(
            1, int(round(STREAM_CHARS_PER_SEC * self._tick_ms / 1000.0))
        )

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._phase = "idle"  # idle | thinking | answering

        self.setStyleSheet(
            f"""
            QFrame#ChatPanel {{
                background-color: {THEME['chat_bg']};
                border: 1px solid {THEME['chat_border']};
                border-radius: 14px;
            }}
            QTextBrowser {{
                background: transparent;
                border: none;
                color: {THEME['text']};
                font-family: 'Bahnschrift';
                font-size: 14px;
                selection-background-color: {THEME['accent_dim']};
            }}
            QLabel#LiveLabel {{
                color: {THEME['text_dim']};
                font-family: 'Bahnschrift';
                font-size: 12px;
                letter-spacing: 1px;
            }}
            QTextEdit#LiveStream {{
                background-color: {THEME['bg']};
                border: 1px solid {THEME['border']};
                border-radius: 10px;
                color: {THEME['text']};
                font-family: 'Bahnschrift';
                font-size: 14px;
                padding: 8px;
            }}
            QLineEdit {{
                background-color: {THEME['bg']};
                border: 1px solid {THEME['border']};
                border-radius: 8px;
                color: {THEME['text']};
                font-family: 'Bahnschrift';
                font-size: 14px;
                padding: 10px 12px;
            }}
            QPushButton {{
                background-color: {THEME['panel']};
                border: 1px solid {THEME['border']};
                border-radius: 8px;
                color: {THEME['text']};
                font-family: 'Bahnschrift';
                font-size: 13px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{ border-color: {THEME['accent']}; }}
            QPushButton:disabled {{ color: {THEME['text_dim']}; }}
            QPushButton#SendBtn {{
                background-color: {THEME['accent_dim']};
                border-color: {THEME['accent']};
                color: {THEME['text']};
                font-weight: 600;
                min-width: 88px;
            }}
            QPushButton#BackBtn {{
                color: {THEME['text_dim']};
                font-size: 12px;
            }}
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Nurse agent")
        title.setStyleSheet(
            f"color: {THEME['accent']}; font-family: 'Bahnschrift'; "
            f"font-size: 15px; font-weight: 700; letter-spacing: 1px;"
        )
        header.addWidget(title)
        header.addStretch(1)

        back = QtWidgets.QPushButton("← Signals")
        back.setObjectName("BackBtn")
        back.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        back.setToolTip("Return to waveform Signal View")
        back.clicked.connect(self.back_to_signals_requested.emit)
        header.addWidget(back)
        layout.addLayout(header)

        self.transcript = QtWidgets.QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.transcript.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        layout.addWidget(self.transcript, stretch=2)

        self.live_label = QtWidgets.QLabel("")
        self.live_label.setObjectName("LiveLabel")
        self.live_label.setVisible(False)
        layout.addWidget(self.live_label)

        self.live_stream = QtWidgets.QTextEdit()
        self.live_stream.setObjectName("LiveStream")
        self.live_stream.setReadOnly(True)
        self.live_stream.setVisible(False)
        self.live_stream.setMinimumHeight(140)
        layout.addWidget(self.live_stream, stretch=2)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText("Ask the nurse agent…")
        self.input.returnPressed.connect(self._submit)
        row.addWidget(self.input, stretch=1)

        self.send_btn = QtWidgets.QPushButton("Send")
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.clicked.connect(self._submit)
        row.addWidget(self.send_btn)
        layout.addLayout(row)

        self.append_system(
            "Ask a question about your baby’s vitals or care. "
            "Replies use the live belt readings shown on the left."
        )

    def focus_input(self) -> None:
        if not self._busy:
            self.input.setFocus(QtCore.Qt.OtherFocusReason)

    def _submit(self) -> None:
        if self._busy:
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.message_submitted.emit(text)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.input.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)

    def append_system(self, text: str) -> None:
        self._append_html(
            f"<p style='color:{THEME['text_dim']}; margin:4px 0;'><i>{_esc(text)}</i></p>"
        )

    def append_user(self, text: str) -> None:
        self._append_html(
            f"<p style='margin:10px 0 4px 0;'>"
            f"<span style='color:{THEME['accent']}; font-weight:700;'>You</span><br>"
            f"<span style='color:{THEME['text']};'>{_esc(text)}</span></p>"
        )

    def start_streamed_reply(
        self,
        *,
        title: str,
        thinking_steps: list[str],
        answer_text: str,
    ) -> None:
        """Show thinking steps, then stream the answer."""
        if self._busy:
            self._timer.stop()
        self.set_busy(True)
        self._stream_title = title
        self._think_steps = list(thinking_steps)
        self._think_i = 0
        self._answer_full = answer_text
        self._answer_i = 0
        self._phase = "thinking"

        self.live_label.setVisible(True)
        self.live_stream.setVisible(True)
        self.live_label.setText("Thinking…")
        self.live_stream.clear()
        self.live_stream.setTextColor(QtGui.QColor(THEME["text_dim"]))
        self.live_stream.append(f"{title}\n")
        self.live_stream.append("Reasoning\n")

        self._timer.setInterval(THINK_STEP_MS)
        self._timer.start()

    def _on_tick(self) -> None:
        if self._phase == "thinking":
            if self._think_i < len(self._think_steps):
                step = self._think_steps[self._think_i]
                self._think_i += 1
                self.live_label.setText(
                    f"Thinking… ({self._think_i}/{len(self._think_steps)})"
                )
                self.live_stream.setTextColor(QtGui.QColor(THEME["text_dim"]))
                self.live_stream.append(f"• {step}")
                self._scroll_live()
                return

            self._phase = "answering"
            self.live_label.setText("Generating…")
            self.live_stream.setTextColor(QtGui.QColor(THEME["text"]))
            self.live_stream.append("\nAnswer\n")
            self._timer.setInterval(self._tick_ms)
            return

        if self._phase == "answering":
            if self._answer_i >= len(self._answer_full):
                self._finish_stream()
                return
            end = min(len(self._answer_full), self._answer_i + self._chars_per_tick)
            chunk = self._answer_full[self._answer_i : end]
            self._answer_i = end
            cursor = self.live_stream.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            self.live_stream.setTextCursor(cursor)
            self.live_stream.setTextColor(QtGui.QColor(THEME["text"]))
            self.live_stream.insertPlainText(chunk)
            self._scroll_live()
            return

        self._timer.stop()

    def _finish_stream(self) -> None:
        self._timer.stop()
        self._phase = "idle"
        self.append_nurse(self._answer_full, title=self._stream_title)
        self.live_stream.clear()
        self.live_stream.setVisible(False)
        self.live_label.setVisible(False)
        self.live_label.setText("")
        self.set_busy(False)
        self.focus_input()

    def append_nurse(self, text: str, title: str | None = None) -> None:
        head = title or "Nurse"
        body = _esc(text).replace("\n", "<br>")
        self._append_html(
            f"<p style='margin:10px 0 4px 0;'>"
            f"<span style='color:{THEME['live']}; font-weight:700;'>{_esc(head)}</span><br>"
            f"<span style='color:{THEME['text']}; line-height:1.45;'>{body}</span></p>"
        )

    def _scroll_live(self) -> None:
        bar = self.live_stream.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _append_html(self, html: str) -> None:
        self.transcript.append(html)
        self.transcript.verticalScrollBar().setValue(
            self.transcript.verticalScrollBar().maximum()
        )


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
