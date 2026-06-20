from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QColor, QPen


_DRAG_NONE = 0
_DRAG_PLAYHEAD = 1
_DRAG_LOOP_A = 2
_DRAG_LOOP_B = 3
_HIT_RADIUS = 8


class ScrubberWidget(QWidget):
    seek_requested = pyqtSignal(float)
    loop_start_changed = pyqtSignal(float)
    loop_end_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(32)
        self._position: float = 0.0
        self._loop_start: float = 0.0
        self._loop_end: float = 1.0
        self._loop_enabled: bool = False
        self._drag: int = _DRAG_NONE

    def set_position(self, fraction: float) -> None:
        self._position = fraction
        self.update()

    def set_loop_start(self, fraction: float) -> None:
        self._loop_start = fraction
        self.update()

    def set_loop_end(self, fraction: float) -> None:
        self._loop_end = fraction
        self.update()

    def set_loop_enabled(self, enabled: bool) -> None:
        self._loop_enabled = enabled
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h // 2
        track_h = 4

        # Grey track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#333333'))
        painter.drawRoundedRect(0, mid_y - track_h // 2, w, track_h, 2, 2)

        # Blue played region
        played_x = int(self._position * w)
        painter.setBrush(QColor('#7c83f5'))
        painter.drawRoundedRect(0, mid_y - track_h // 2, played_x, track_h, 2, 2)

        if self._loop_enabled:
            # Orange loop region
            lx = int(self._loop_start * w)
            lw = int((self._loop_end - self._loop_start) * w)
            loop_color = QColor('#f39c12')
            loop_color.setAlpha(80)
            painter.setBrush(loop_color)
            painter.drawRect(lx, mid_y - track_h // 2, lw, track_h)

            # A marker
            painter.setPen(QPen(QColor('#f39c12'), 2))
            painter.setBrush(QColor('#f39c12'))
            painter.drawLine(lx, mid_y - 10, lx, mid_y + 10)
            painter.setPen(QColor('#f39c12'))
            painter.drawText(lx + 3, mid_y - 8, 'A')

            # B marker
            bx = int(self._loop_end * w)
            painter.setPen(QPen(QColor('#f39c12'), 2))
            painter.drawLine(bx, mid_y - 10, bx, mid_y + 10)
            painter.setPen(QColor('#f39c12'))
            painter.drawText(bx + 3, mid_y - 8, 'B')

        # White playhead
        px = int(self._position * w)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(px - 6, mid_y - 6, 12, 12)

    def mousePressEvent(self, event):
        x = event.position().x()
        w = self.width()
        fraction = max(0.0, min(1.0, x / w))

        px = int(self._position * w)
        ax = int(self._loop_start * w)
        bx = int(self._loop_end * w)

        if self._loop_enabled and abs(x - ax) < _HIT_RADIUS:
            self._drag = _DRAG_LOOP_A
        elif self._loop_enabled and abs(x - bx) < _HIT_RADIUS:
            self._drag = _DRAG_LOOP_B
        elif abs(x - px) < _HIT_RADIUS:
            self._drag = _DRAG_PLAYHEAD
            self.seek_requested.emit(fraction)
        else:
            self._drag = _DRAG_NONE
            self.seek_requested.emit(fraction)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        fraction = max(0.0, min(1.0, x / self.width()))
        if self._drag == _DRAG_PLAYHEAD:
            self.seek_requested.emit(fraction)
        elif self._drag == _DRAG_LOOP_A:
            self.loop_start_changed.emit(fraction)
        elif self._drag == _DRAG_LOOP_B:
            self.loop_end_changed.emit(fraction)

    def mouseReleaseEvent(self, event):
        self._drag = _DRAG_NONE


from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGroupBox,
)
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from pathlib import Path
from stem_splitter.core.output import STEMS
from stem_splitter.core.player import PlayerEngine
import sounddevice as sd


def _fmt(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


class StretchWorker(QThread):
    finished = pyqtSignal()

    def __init__(self, engine: PlayerEngine, rate: float, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._rate = rate

    def run(self):
        self._engine.stretch(self._rate)
        self.finished.emit()


class PlayerWindow(QDialog):
    def __init__(self, output_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stem Player")
        self.setMinimumWidth(440)

        stem_paths = {stem: output_dir / f"{stem}.wav" for stem in STEMS}
        self._engine = PlayerEngine(stem_paths)
        self._stretch_worker: StretchWorker | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_mixer_strips())
        layout.addWidget(self._build_scrubber_section())
        layout.addWidget(self._build_transport())
        layout.addWidget(self._build_loop_controls())
        layout.addWidget(self._build_speed_control())

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        if parent is not None:
            self.move(parent.geometry().right() + 8, parent.geometry().top())

    def _build_mixer_strips(self) -> QGroupBox:
        box = QGroupBox("Stems")
        layout = QVBoxLayout(box)
        self._mute_btns: dict[str, QPushButton] = {}
        self._solo_btns: dict[str, QPushButton] = {}
        self._vol_labels: dict[str, QLabel] = {}

        for stem in STEMS:
            row = QHBoxLayout()
            available = stem in self._engine.available_stems

            name = QLabel(stem)
            name.setFixedWidth(55)
            row.addWidget(name)

            m_btn = QPushButton("M")
            m_btn.setFixedWidth(28)
            m_btn.setCheckable(True)
            m_btn.setEnabled(available)
            m_btn.toggled.connect(lambda checked, s=stem: self._on_mute(s, checked))
            self._mute_btns[stem] = m_btn
            row.addWidget(m_btn)

            s_btn = QPushButton("S")
            s_btn.setFixedWidth(28)
            s_btn.setCheckable(True)
            s_btn.setEnabled(available)
            s_btn.toggled.connect(lambda checked, s=stem: self._on_solo(s, checked))
            self._solo_btns[stem] = s_btn
            row.addWidget(s_btn)

            vol_slider = QSlider(Qt.Orientation.Horizontal)
            vol_slider.setRange(0, 100)
            vol_slider.setValue(100)
            vol_slider.setEnabled(available)
            vol_label = QLabel("100%")
            vol_label.setFixedWidth(38)
            self._vol_labels[stem] = vol_label
            vol_slider.valueChanged.connect(
                lambda v, s=stem, lbl=vol_label: self._on_volume(s, v, lbl)
            )
            row.addWidget(vol_slider)
            row.addWidget(vol_label)

            if not available:
                name.setStyleSheet("color: #555;")

            layout.addLayout(row)
        return box

    def _on_mute(self, stem: str, checked: bool) -> None:
        self._engine.set_mute(stem, checked)
        btn = self._mute_btns[stem]
        btn.setStyleSheet(
            "color: #e74c3c; border: 1px solid #e74c3c;" if checked else ""
        )

    def _on_solo(self, stem: str, checked: bool) -> None:
        self._engine.set_solo(stem, checked)
        btn = self._solo_btns[stem]
        btn.setStyleSheet(
            "color: #2ecc71; border: 1px solid #2ecc71;" if checked else ""
        )

    def _on_volume(self, stem: str, value: int, label: QLabel) -> None:
        self._engine.set_volume(stem, value / 100.0)
        label.setText(f"{value}%")

    def _build_scrubber_section(self) -> QWidget:
        from PyQt6.QtWidgets import QWidget as _W
        w = _W()
        row = QHBoxLayout(w)
        self._time_label = QLabel("0:00 / 0:00")
        self._scrubber = ScrubberWidget()
        self._scrubber.seek_requested.connect(self._engine.seek)
        self._scrubber.loop_start_changed.connect(self._engine.set_loop_start)
        self._scrubber.loop_end_changed.connect(self._engine.set_loop_end)
        row.addWidget(self._time_label)
        row.addWidget(self._scrubber)
        return w

    def _build_transport(self) -> QWidget:
        from PyQt6.QtWidgets import QWidget as _W
        w = _W()
        row = QHBoxLayout(w)
        self._play_btn = QPushButton("▶ Play")
        self._play_btn.clicked.connect(self._on_play_pause)
        stop_btn = QPushButton("■ Stop")
        stop_btn.clicked.connect(self._on_stop)
        row.addStretch()
        row.addWidget(self._play_btn)
        row.addWidget(stop_btn)
        row.addStretch()
        return w

    def _on_play_pause(self) -> None:
        if self._engine.is_playing:
            self._engine.pause()
        else:
            try:
                self._engine.play()
            except sd.PortAudioError as exc:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Audio Error",
                                    f"No audio output device found:\n{exc}")

    def _on_stop(self) -> None:
        self._engine.stop()
        self._scrubber.set_position(0.0)

    def _build_loop_controls(self) -> QGroupBox:
        box = QGroupBox("Loop")
        row = QHBoxLayout(box)

        self._loop_btn = QPushButton("⟳ Loop")
        self._loop_btn.setCheckable(True)
        self._loop_btn.toggled.connect(self._on_loop_toggle)
        row.addWidget(self._loop_btn)

        set_a_btn = QPushButton("Set A")
        set_a_btn.clicked.connect(self._on_set_a)
        row.addWidget(set_a_btn)

        set_b_btn = QPushButton("Set B")
        set_b_btn.clicked.connect(self._on_set_b)
        row.addWidget(set_b_btn)

        self._loop_label = QLabel("A: — / B: —")
        row.addWidget(self._loop_label)
        row.addStretch()
        return box

    def _on_loop_toggle(self, checked: bool) -> None:
        self._engine.set_loop_enabled(checked)
        self._scrubber.set_loop_enabled(checked)
        self._loop_btn.setStyleSheet(
            "color: #f39c12; border: 1px solid #f39c12;" if checked else ""
        )

    def _on_set_a(self) -> None:
        pos = self._engine.position
        self._engine.set_loop_start(pos)
        self._scrubber.set_loop_start(pos)
        self._update_loop_label()

    def _on_set_b(self) -> None:
        pos = self._engine.position
        self._engine.set_loop_end(pos)
        self._scrubber.set_loop_end(pos)
        self._update_loop_label()

    def _update_loop_label(self) -> None:
        a_sec, b_sec = self._engine.loop_bounds_seconds()
        self._loop_label.setText(f"A: {_fmt(a_sec)}  B: {_fmt(b_sec)}")

    def _build_speed_control(self) -> QGroupBox:
        box = QGroupBox("Speed")
        row = QHBoxLayout(box)

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(25, 100)
        self._speed_slider.setSingleStep(5)
        self._speed_slider.setValue(100)
        self._speed_label = QLabel("100%")
        self._speed_label.setFixedWidth(38)
        self._speed_slider.valueChanged.connect(
            lambda v: self._speed_label.setText(f"{v}%")
        )
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply_speed)
        self._processing_label = QLabel("Processing…")
        self._processing_label.setVisible(False)

        row.addWidget(self._speed_slider)
        row.addWidget(self._speed_label)
        row.addWidget(self._apply_btn)
        row.addWidget(self._processing_label)
        return box

    def _on_apply_speed(self) -> None:
        rate = self._speed_slider.value() / 100.0
        was_playing = self._engine.is_playing
        self._engine.pause()
        self._apply_btn.setEnabled(False)
        self._processing_label.setVisible(True)

        self._stretch_worker = StretchWorker(self._engine, rate, parent=self)
        self._stretch_worker.finished.connect(
            lambda: self._on_stretch_done(was_playing)
        )
        self._stretch_worker.start()

    def _on_stretch_done(self, resume: bool) -> None:
        self._processing_label.setVisible(False)
        self._apply_btn.setEnabled(True)
        if resume:
            try:
                self._engine.play()
            except sd.PortAudioError as exc:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Audio Error",
                                    f"No audio output device found:\n{exc}")

    def _on_tick(self) -> None:
        pos = self._engine.position
        self._scrubber.set_position(pos)
        dur = self._engine.duration
        elapsed = pos * dur
        self._time_label.setText(f"{_fmt(elapsed)} / {_fmt(dur)}")
        self._play_btn.setText('⏸ Pause' if self._engine.is_playing else '▶ Play')
        if self._loop_btn.isChecked() and dur > 0:
            a_sec, b_sec = self._engine.loop_bounds_seconds()
            self._scrubber.set_loop_start(a_sec / dur)
            self._scrubber.set_loop_end(b_sec / dur)

    def closeEvent(self, event):
        self._timer.stop()
        self._engine.stop()
        super().closeEvent(event)
