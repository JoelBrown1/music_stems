from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QColor, QPen


_DRAG_NONE = 0
_DRAG_PLAYHEAD = 1
_DRAG_LOOP_A = 2
_DRAG_LOOP_B = 3
_DRAG_PAN = 4
_HIT_RADIUS = 8



from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGroupBox, QLineEdit, QScrollBar,
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


def _measure_fractions(bpm: float, numerator: int, duration: float) -> list[tuple[float, int]]:
    if bpm <= 0 or duration <= 0:
        return []
    seconds_per_measure = (60.0 / bpm) * numerator
    result: list[tuple[float, int]] = []
    t = 0.0
    m = 1
    while t <= duration + 1e-9:
        result.append((t / duration, m))
        t += seconds_per_measure
        m += 1
    return result


def _beat_fractions(bpm: float, numerator: int, duration: float) -> list[float]:
    if bpm <= 0 or duration <= 0:
        return []
    seconds_per_beat = 60.0 / bpm
    result: list[float] = []
    beat_index = 1
    t = seconds_per_beat
    while t < duration - 1e-9:
        if beat_index % numerator != 0:
            result.append(t / duration)
        t += seconds_per_beat
        beat_index += 1
    return result


_MIN_SPAN: float = 1.0 / 64.0  # minimum view window (fraction of total song)
_AUTO_PAN_MARGIN: float = 0.05  # fraction of view span that triggers auto-pan


def _to_screen(fraction: float, view_start: float, view_end: float, width: int) -> int:
    """Map a song fraction to a screen x-coordinate within the current view window."""
    span = view_end - view_start
    if span <= 0:
        return 0
    return int((fraction - view_start) / span * width)


def _to_fraction(x: float, view_start: float, view_end: float, width: int) -> float:
    """Map a screen x-coordinate to a song fraction within the current view window."""
    if width <= 0:
        return view_start
    span = view_end - view_start
    return view_start + (x / width) * span


def _clamp_window(start: float, end: float) -> tuple[float, float]:
    """Clamp a view window to [0, 1], preserving span and enforcing _MIN_SPAN."""
    span = max(_MIN_SPAN, min(1.0, end - start))
    if start < 0.0:
        return 0.0, span
    if start + span > 1.0:
        return max(0.0, 1.0 - span), 1.0
    return start, start + span


def _zoom_centered(
    view_start: float, view_end: float, factor: float, center: float
) -> tuple[float, float]:
    """Scale the view window span by factor, keeping center fixed.
    Enforces _MIN_SPAN minimum and [0, 1] bounds. Returns clamped (start, end)."""
    span = view_end - view_start
    if span <= 0:
        span = _MIN_SPAN
    new_span = max(_MIN_SPAN, min(1.0, span * factor))
    ratio = new_span / span
    new_start = center - (center - view_start) * ratio
    return _clamp_window(new_start, new_start + new_span)


def _nearest_beat_fraction(fraction: float, bpm: float, duration: float) -> float:
    """Return the nearest beat boundary as a song fraction. Returns fraction unchanged if bpm/duration ≤ 0."""
    if bpm <= 0 or duration <= 0:
        return fraction
    spb = 60.0 / bpm
    t = fraction * duration
    nearest_t = round(t / spb) * spb
    return max(0.0, min(1.0, nearest_t / duration))


def _should_snap(
    fraction: float,
    nearest: float,
    view_start: float,
    view_end: float,
    width: int,
    threshold_px: int = 10,
) -> bool:
    """True if nearest beat is within threshold_px of fraction in screen coordinates."""
    sx = _to_screen(fraction, view_start, view_end, width)
    nx = _to_screen(nearest, view_start, view_end, width)
    return abs(sx - nx) <= threshold_px


class OverviewStrip(QWidget):
    """Always-full-song overview strip. Shows position, loop region, measure lines,
    and a shaded box indicating the current detail view window."""

    seek_requested = pyqtSignal(float)
    view_pan_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._position: float = 0.0
        self._loop_start: float = 0.0
        self._loop_end: float = 1.0
        self._loop_enabled: bool = False
        self._bpm: float = 0.0
        self._ts_numerator: int = 4
        self._duration: float = 0.0
        self._view_start: float = 0.0
        self._view_end: float = 1.0
        self._dragging_box: bool = False
        self._drag_box_offset: float = 0.0

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

    def set_tempo(self, bpm: float, numerator: int, denominator: int, duration: float) -> None:
        self._bpm = bpm
        self._ts_numerator = numerator
        self._duration = duration
        self.update()

    def set_view_window(self, start: float, end: float) -> None:
        self._view_start = start
        self._view_end = end
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h // 2
        bar_h = 3

        # Grey track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#333333'))
        painter.drawRect(0, mid_y - bar_h // 2, w, bar_h)

        # Played region
        played_x = int(self._position * w)
        painter.setBrush(QColor('#7c83f5'))
        painter.drawRect(0, mid_y - bar_h // 2, played_x, bar_h)

        # Loop region and markers
        if self._loop_enabled:
            lx = int(self._loop_start * w)
            bx = int(self._loop_end * w)
            lc = QColor('#f39c12')
            lc.setAlpha(80)
            painter.setBrush(lc)
            painter.drawRect(lx, mid_y - bar_h // 2, bx - lx, bar_h)
            painter.setPen(QPen(QColor('#f39c12'), 1))
            painter.drawLine(lx, 0, lx, h)
            painter.drawLine(bx, 0, bx, h)

        # Measure lines (no numbers — too small)
        if self._bpm > 0 and self._duration > 0:
            mc = QColor('#7c83f5')
            mc.setAlpha(60)
            painter.setPen(QPen(mc, 1))
            for frac, _ in _measure_fractions(self._bpm, self._ts_numerator, self._duration):
                mx = int(frac * w)
                painter.drawLine(mx, mid_y - bar_h // 2, mx, mid_y + bar_h // 2)

        # Playhead
        px = int(self._position * w)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(px - 3, mid_y - 3, 6, 6)

        # View window box
        vx = int(self._view_start * w)
        vw = int((self._view_end - self._view_start) * w)
        vc = QColor('#ffffff')
        vc.setAlpha(25)
        painter.setBrush(vc)
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawRect(vx, 0, vw, h - 1)

    def mousePressEvent(self, event):
        x = event.position().x()
        w = self.width()
        fraction = max(0.0, min(1.0, x / w))
        vx = int(self._view_start * w)
        vw = int((self._view_end - self._view_start) * w)
        if vw > 0 and vx <= x <= vx + vw:
            self._dragging_box = True
            center = (self._view_start + self._view_end) / 2
            self._drag_box_offset = fraction - center
        else:
            self._dragging_box = False
            self.seek_requested.emit(fraction)
            self.view_pan_requested.emit(fraction)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        fraction = max(0.0, min(1.0, x / self.width()))
        if self._dragging_box:
            self.view_pan_requested.emit(fraction - self._drag_box_offset)
        else:
            self.seek_requested.emit(fraction)

    def mouseReleaseEvent(self, event):
        self._dragging_box = False


class DetailTimeline(QWidget):
    """Zoomable detail timeline for precise loop A/B editing.

    View window [_view_start, _view_end] maps song fractions to screen pixels.
    All painting and hit-testing go through _screen()/_fraction() helpers.
    Playhead auto-follows when playing. Dragged A/B markers auto-pan at the edges.
    Holding ⌘ (Command) while dragging A/B snaps to the nearest beat.
    """

    seek_requested = pyqtSignal(float)
    loop_start_changed = pyqtSignal(float)
    loop_end_changed = pyqtSignal(float)
    zoom_changed = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self._position: float = 0.0
        self._loop_start: float = 0.0
        self._loop_end: float = 1.0
        self._loop_enabled: bool = False
        self._bpm: float = 0.0
        self._ts_numerator: int = 4
        self._ts_denominator: int = 4
        self._duration: float = 0.0
        self._view_start: float = 0.0
        self._view_end: float = 1.0
        self._drag: int = _DRAG_NONE
        self._pan_anchor_frac: float = 0.0
        self._snapping: bool = False

    # ------------------------------------------------------------------ public

    def set_position(self, fraction: float) -> None:
        self._position = fraction
        if not (self._view_start <= fraction <= self._view_end):
            span = self._view_end - self._view_start
            new_start, new_end = _clamp_window(fraction - span / 2, fraction + span / 2)
            self._view_start = new_start
            self._view_end = new_end
            self.zoom_changed.emit(new_start, new_end)
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

    def set_tempo(self, bpm: float, numerator: int, denominator: int, duration: float) -> None:
        self._bpm = bpm
        self._ts_numerator = numerator
        self._ts_denominator = denominator
        self._duration = duration
        self.update()

    def set_view_window(self, start: float, end: float) -> None:
        self._view_start = start
        self._view_end = end
        self.update()

    # ----------------------------------------------------------------- helpers

    def _screen(self, fraction: float) -> int:
        return _to_screen(fraction, self._view_start, self._view_end, self.width())

    def _fraction(self, x: float) -> float:
        return _to_fraction(x, self._view_start, self._view_end, self.width())

    def _apply_auto_pan(self, fraction: float) -> None:
        span = self._view_end - self._view_start
        margin = span * _AUTO_PAN_MARGIN
        shift = 0.0
        if fraction < self._view_start + margin:
            shift = fraction - (self._view_start + margin)
        elif fraction > self._view_end - margin:
            shift = fraction - (self._view_end - margin)
        if shift != 0.0:
            new_start, new_end = _clamp_window(
                self._view_start + shift, self._view_end + shift
            )
            self._view_start = new_start
            self._view_end = new_end
            self.zoom_changed.emit(new_start, new_end)

    def _resolve_snap(self, fraction: float) -> float:
        from PyQt6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers()
        if Qt.KeyboardModifier.ControlModifier in mods:
            nearest = _nearest_beat_fraction(fraction, self._bpm, self._duration)
            if _should_snap(fraction, nearest, self._view_start, self._view_end, self.width()):
                self._snapping = True
                return nearest
        self._snapping = False
        return fraction

    # ----------------------------------------------------------------- painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h // 2
        track_h = 6

        # Grey track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#333333'))
        painter.drawRoundedRect(0, mid_y - track_h // 2, w, track_h, 2, 2)

        # Played region (only the portion visible in the current view window)
        if self._position <= self._view_start:
            played_to = 0
        elif self._position >= self._view_end:
            played_to = w
        else:
            played_to = self._screen(self._position)
        played_to = max(0, min(w, played_to))
        painter.setBrush(QColor('#7c83f5'))
        painter.drawRoundedRect(0, mid_y - track_h // 2, played_to, track_h, 2, 2)

        # Loop region and A/B markers
        if self._loop_enabled:
            lx = self._screen(self._loop_start)
            bx = self._screen(self._loop_end)
            lc = QColor('#f39c12')
            lc.setAlpha(80)
            painter.setBrush(lc)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(lx, mid_y - track_h // 2, bx - lx, track_h)

            a_color = QColor('#ffffff') if (self._snapping and self._drag == _DRAG_LOOP_A) else QColor('#f39c12')
            b_color = QColor('#ffffff') if (self._snapping and self._drag == _DRAG_LOOP_B) else QColor('#f39c12')

            painter.setPen(QPen(a_color, 2))
            painter.drawLine(lx, mid_y - 12, lx, mid_y + 12)
            painter.setPen(a_color)
            painter.drawText(lx + 3, mid_y - 10, 'A')

            painter.setPen(QPen(b_color, 2))
            painter.drawLine(bx, mid_y - 12, bx, mid_y + 12)
            painter.setPen(b_color)
            painter.drawText(bx + 3, mid_y - 10, 'B')

        # Beat dots and measure lines (skip anything outside the visible range)
        if self._bpm > 0 and self._duration > 0:
            bar_y = mid_y - track_h // 2

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#444444'))
            for frac in _beat_fractions(self._bpm, self._ts_numerator, self._duration):
                bx2 = self._screen(frac)
                if 0 <= bx2 <= w:
                    painter.drawEllipse(bx2 - 1, mid_y - 1, 3, 3)

            small_font = painter.font()
            small_font.setPointSize(7)
            painter.setFont(small_font)
            for frac, num in _measure_fractions(self._bpm, self._ts_numerator, self._duration):
                mx = self._screen(frac)
                if -2 <= mx <= w + 2:
                    lc2 = QColor('#7c83f5')
                    lc2.setAlpha(0xb0 if num == 1 else 0x60)
                    painter.setPen(QPen(lc2, 1))
                    painter.drawLine(mx, bar_y, mx, bar_y + track_h)
                    tc = QColor('#7c83f5') if num == 1 else QColor('#666666')
                    painter.setPen(tc)
                    painter.drawText(mx + 2, bar_y - 2, str(num))

        # Playhead (always on top)
        px = self._screen(self._position)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(px - 6, mid_y - 6, 12, 12)

    # -------------------------------------------------------------- mouse / wheel

    def mousePressEvent(self, event):
        x = event.position().x()
        fraction = max(0.0, min(1.0, self._fraction(x)))
        px = self._screen(self._position)
        ax = self._screen(self._loop_start)
        bx = self._screen(self._loop_end)

        if self._loop_enabled and abs(x - ax) < _HIT_RADIUS:
            self._drag = _DRAG_LOOP_A
        elif self._loop_enabled and abs(x - bx) < _HIT_RADIUS:
            self._drag = _DRAG_LOOP_B
        elif abs(x - px) < _HIT_RADIUS:
            self._drag = _DRAG_PLAYHEAD
            self.seek_requested.emit(fraction)
        else:
            self._drag = _DRAG_PAN
            self._pan_anchor_frac = self._fraction(x)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        fraction = max(0.0, min(1.0, self._fraction(x)))
        if self._drag == _DRAG_PLAYHEAD:
            self.seek_requested.emit(fraction)
        elif self._drag == _DRAG_LOOP_A:
            fraction = self._resolve_snap(fraction)
            self._apply_auto_pan(fraction)
            self.loop_start_changed.emit(fraction)
        elif self._drag == _DRAG_LOOP_B:
            fraction = self._resolve_snap(fraction)
            self._apply_auto_pan(fraction)
            self.loop_end_changed.emit(fraction)
        elif self._drag == _DRAG_PAN:
            delta = self._pan_anchor_frac - self._fraction(x)
            new_start, new_end = _clamp_window(
                self._view_start + delta, self._view_end + delta
            )
            self._view_start = new_start
            self._view_end = new_end
            self.zoom_changed.emit(new_start, new_end)
            self._pan_anchor_frac = self._fraction(x)
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = _DRAG_NONE
        self._snapping = False
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 0.8 if delta > 0 else 1.25
        center = self._fraction(event.position().x())
        new_start, new_end = _zoom_centered(
            self._view_start, self._view_end, factor, center
        )
        self._view_start = new_start
        self._view_end = new_end
        self.zoom_changed.emit(new_start, new_end)
        self.update()


class ZoomControlBar(QWidget):
    """Zoom −/+ buttons, zoom-to-loop button, reset button, and a pan scrollbar."""

    zoom_changed = pyqtSignal(float, float)
    reset_requested = pyqtSignal()
    zoom_to_loop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_start: float = 0.0
        self._view_end: float = 1.0
        self._updating_scrollbar: bool = False

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 2, 0, 0)
        col.setSpacing(2)

        btn_row = QWidget()
        row = QHBoxLayout(btn_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        minus_btn = QPushButton("−")
        minus_btn.setFixedWidth(28)
        minus_btn.clicked.connect(self._on_zoom_out)
        row.addWidget(minus_btn)

        plus_btn = QPushButton("+")
        plus_btn.setFixedWidth(28)
        plus_btn.clicked.connect(self._on_zoom_in)
        row.addWidget(plus_btn)

        self._loop_btn = QPushButton("⊡ Zoom to loop")
        self._loop_btn.setEnabled(False)
        self._loop_btn.clicked.connect(self.zoom_to_loop_requested)
        row.addWidget(self._loop_btn)

        reset_btn = QPushButton("↺")
        reset_btn.setFixedWidth(28)
        reset_btn.clicked.connect(self.reset_requested)
        row.addWidget(reset_btn)
        row.addStretch()

        self._scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._scrollbar.setRange(0, 10000)
        self._scrollbar.setVisible(False)
        self._scrollbar.valueChanged.connect(self._on_scroll)

        col.addWidget(btn_row)
        col.addWidget(self._scrollbar)

    def set_view_window(self, start: float, end: float) -> None:
        self._view_start = start
        self._view_end = end
        self._update_scrollbar()

    def set_loop_zoom_enabled(self, enabled: bool) -> None:
        self._loop_btn.setEnabled(enabled)

    def _update_scrollbar(self) -> None:
        span = self._view_end - self._view_start
        is_zoomed = span < 0.999
        self._scrollbar.setVisible(is_zoomed)
        if not is_zoomed:
            return
        self._updating_scrollbar = True
        page = max(1, int(span * 10000))
        self._scrollbar.setPageStep(page)
        self._scrollbar.setMaximum(10000 - page)
        self._scrollbar.setValue(int(self._view_start * 10000))
        self._updating_scrollbar = False

    def _on_scroll(self, value: int) -> None:
        if self._updating_scrollbar:
            return
        span = self._view_end - self._view_start
        new_start = value / 10000.0
        new_end = new_start + span
        if new_end > 1.0:
            new_end = 1.0
            new_start = max(0.0, 1.0 - span)
        self.zoom_changed.emit(new_start, new_end)

    def _on_zoom_in(self) -> None:
        center = (self._view_start + self._view_end) / 2
        s, e = _zoom_centered(self._view_start, self._view_end, 0.5, center)
        self.zoom_changed.emit(s, e)

    def _on_zoom_out(self) -> None:
        center = (self._view_start + self._view_end) / 2
        s, e = _zoom_centered(self._view_start, self._view_end, 2.0, center)
        self.zoom_changed.emit(s, e)


class StretchWorker(QThread):
    finished = pyqtSignal()

    def __init__(self, engine: PlayerEngine, rate: float, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._rate = rate

    def run(self):
        self._engine.stretch(self._rate)
        self.finished.emit()


class BpmDetectWorker(QThread):
    detected = pyqtSignal(float)

    def __init__(self, engine: PlayerEngine, parent=None):
        super().__init__(parent)
        self._engine = engine

    def run(self) -> None:
        try:
            import librosa
            import numpy as np
            # Safe to read without lock: detection runs at load, before any stretch modifies _arrays
            arrays = self._engine._arrays
            available = self._engine._available
            sr = self._engine._sample_rate
            if not available or not arrays:
                self.detected.emit(0.0)
                return
            # Build mono mix: average left+right channels across all stems
            stems = []
            for s in available:
                if s not in arrays:
                    continue
                a = arrays[s]
                stems.append(a[:, 0] if a.shape[1] == 1 else (a[:, 0] + a[:, 1]) * 0.5)
            max_len = max(a.shape[0] for a in stems)
            mix = np.zeros(max_len, dtype='float32')
            for stem_mono in stems:
                mix[:stem_mono.shape[0]] += stem_mono
            mix /= len(stems)
            tempo, _ = librosa.beat.beat_track(y=mix, sr=sr)
            bpm = float(np.atleast_1d(tempo)[0])
            if not (40.0 <= bpm <= 250.0):
                self.detected.emit(0.0)
                return
            self.detected.emit(float(round(bpm)))
        except Exception:
            self.detected.emit(0.0)


_VALID_DENOMINATORS = {1, 2, 4, 8, 16}


class TempoInfoBar(QWidget):
    tempo_changed = pyqtSignal(float, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bpm: float = 0.0
        self._numerator: int = 4
        self._denominator: int = 4

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._bpm_label = QLabel('… BPM')
        self._bpm_label.setStyleSheet('color: #7c83f5; font-weight: bold;')
        self._bpm_label.mouseDoubleClickEvent = self._edit_bpm
        row.addWidget(self._bpm_label)

        self._num_label = QLabel('4')
        self._num_label.mouseDoubleClickEvent = self._edit_numerator
        row.addWidget(self._num_label)

        row.addWidget(QLabel('/'))

        self._den_label = QLabel('4')
        self._den_label.mouseDoubleClickEvent = self._edit_denominator
        row.addWidget(self._den_label)

        row.addStretch()

        self._time_label = QLabel('0:00 / 0:00')
        self._time_label.setStyleSheet('color: #555;')
        row.addWidget(self._time_label)

    def set_bpm(self, bpm: float) -> None:
        self._bpm = bpm
        self._bpm_label.setText('? BPM' if bpm == 0.0 else f'{int(bpm)} BPM')

    def update_time(self, elapsed: float, duration: float) -> None:
        self._time_label.setText(f'{_fmt(elapsed)} / {_fmt(duration)}')

    def _edit_bpm(self, event) -> None:
        edit = QLineEdit(str(int(self._bpm)) if self._bpm > 0 else '', self)
        edit.setFixedWidth(60)
        edit.move(self._bpm_label.pos())
        edit.show()
        edit.setFocus()
        edit.selectAll()

        def commit():
            edit.editingFinished.disconnect(commit)  # guard: editingFinished can fire twice on Enter
            try:
                val = float(edit.text())
                if 40.0 <= val <= 250.0:
                    self._bpm = val
                    self._bpm_label.setText(f'{int(val)} BPM')
                    self.tempo_changed.emit(self._bpm, self._numerator, self._denominator)
            except ValueError:
                pass
            edit.deleteLater()

        edit.editingFinished.connect(commit)

    def _edit_numerator(self, event) -> None:
        edit = QLineEdit(str(self._numerator), self)
        edit.setFixedWidth(30)
        edit.move(self._num_label.pos())
        edit.show()
        edit.setFocus()
        edit.selectAll()

        def commit():
            edit.editingFinished.disconnect(commit)  # guard: editingFinished can fire twice on Enter
            try:
                val = int(edit.text())
                if 1 <= val <= 16:
                    self._numerator = val
                    self._num_label.setText(str(val))
                    self.tempo_changed.emit(self._bpm, self._numerator, self._denominator)
            except ValueError:
                pass
            edit.deleteLater()

        edit.editingFinished.connect(commit)

    def _edit_denominator(self, event) -> None:
        edit = QLineEdit(str(self._denominator), self)
        edit.setFixedWidth(30)
        edit.move(self._den_label.pos())
        edit.show()
        edit.setFocus()
        edit.selectAll()

        def commit():
            edit.editingFinished.disconnect(commit)  # guard: editingFinished can fire twice on Enter
            try:
                val = int(edit.text())
                if val in _VALID_DENOMINATORS:
                    self._denominator = val
                    self._den_label.setText(str(val))
                    self.tempo_changed.emit(self._bpm, self._numerator, self._denominator)
            except ValueError:
                pass
            edit.deleteLater()

        edit.editingFinished.connect(commit)


class PlayerWindow(QDialog):
    def __init__(self, output_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stem Player")
        self.setMinimumWidth(440)

        stem_paths = {stem: output_dir / f"{stem}.wav" for stem in STEMS}
        self._engine = PlayerEngine(stem_paths)
        self._stretch_worker: StretchWorker | None = None
        self._bpm_worker: BpmDetectWorker | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_mixer_strips())
        layout.addWidget(self._build_scrubber_section())
        layout.addWidget(self._build_transport())
        layout.addWidget(self._build_loop_controls())
        layout.addWidget(self._build_speed_control())

        self._tempo_bar.tempo_changed.connect(self._on_tempo_changed)
        self._bpm_worker = BpmDetectWorker(self._engine, parent=self)
        self._bpm_worker.detected.connect(self._on_bpm_detected)
        self._bpm_worker.start()

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        if parent is not None:
            self.move(parent.geometry().right() + 8, parent.geometry().top())

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

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
        from PyQt6.QtWidgets import QWidget as _W, QVBoxLayout
        w = _W()
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        self._tempo_bar = TempoInfoBar()
        self._overview = OverviewStrip()
        self._detail = DetailTimeline()
        self._zoom_bar = ZoomControlBar()

        # Seek
        self._overview.seek_requested.connect(self._engine.seek)
        self._detail.seek_requested.connect(self._engine.seek)

        # Overview pan request → shift detail view window
        self._overview.view_pan_requested.connect(self._on_overview_pan)

        # Loop editing from detail → engine + overview
        self._detail.loop_start_changed.connect(self._engine.set_loop_start)
        self._detail.loop_start_changed.connect(self._overview.set_loop_start)
        self._detail.loop_end_changed.connect(self._engine.set_loop_end)
        self._detail.loop_end_changed.connect(self._overview.set_loop_end)

        # Zoom sync: detail wheel/pan → all three widgets
        self._detail.zoom_changed.connect(self._on_view_changed)

        # Zoom bar buttons/scrollbar → all three widgets
        self._zoom_bar.zoom_changed.connect(self._on_view_changed)
        self._zoom_bar.reset_requested.connect(self._on_zoom_reset)
        self._zoom_bar.zoom_to_loop_requested.connect(self._on_zoom_to_loop)

        col.addWidget(self._tempo_bar)
        col.addWidget(self._overview)
        col.addWidget(self._detail)
        col.addWidget(self._zoom_bar)
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
        self._overview.set_position(0.0)
        self._detail.set_position(0.0)

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
        self._overview.set_loop_enabled(checked)
        self._detail.set_loop_enabled(checked)
        self._loop_btn.setStyleSheet(
            "color: #f39c12; border: 1px solid #f39c12;" if checked else ""
        )
        self._update_loop_zoom_button()

    def _on_set_a(self) -> None:
        pos = self._engine.position
        self._engine.set_loop_start(pos)
        self._overview.set_loop_start(pos)
        self._detail.set_loop_start(pos)
        self._update_loop_label()
        self._update_loop_zoom_button()

    def _on_set_b(self) -> None:
        pos = self._engine.position
        self._engine.set_loop_end(pos)
        self._overview.set_loop_end(pos)
        self._detail.set_loop_end(pos)
        self._update_loop_label()
        self._update_loop_zoom_button()

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
        self._overview.set_position(pos)
        self._detail.set_position(pos)
        dur = self._engine.duration
        self._tempo_bar.update_time(pos * dur, dur)
        self._play_btn.setText('⏸ Pause' if self._engine.is_playing else '▶ Play')
        if self._loop_btn.isChecked() and dur > 0:
            a_sec, b_sec = self._engine.loop_bounds_seconds()
            a_frac = a_sec / dur
            b_frac = b_sec / dur
            self._overview.set_loop_start(a_frac)
            self._overview.set_loop_end(b_frac)
            self._detail.set_loop_start(a_frac)
            self._detail.set_loop_end(b_frac)

    def _on_view_changed(self, start: float, end: float) -> None:
        self._overview.set_view_window(start, end)
        self._detail.set_view_window(start, end)
        self._zoom_bar.set_view_window(start, end)

    def _on_overview_pan(self, center: float) -> None:
        span = self._detail._view_end - self._detail._view_start
        new_start, new_end = _clamp_window(center - span / 2, center + span / 2)
        self._on_view_changed(new_start, new_end)

    def _on_zoom_reset(self) -> None:
        self._on_view_changed(0.0, 1.0)

    def _on_zoom_to_loop(self) -> None:
        a_sec, b_sec = self._engine.loop_bounds_seconds()
        dur = self._engine.duration
        if dur <= 0 or a_sec >= b_sec:
            return
        a_frac = a_sec / dur
        b_frac = b_sec / dur
        margin = (b_frac - a_frac) * 0.1
        s = max(0.0, a_frac - margin)
        e = min(1.0, b_frac + margin)
        min_span = min(1.0, 0.5 / dur) if dur > 0 else _MIN_SPAN
        if e - s < min_span:
            mid = (s + e) / 2
            s, e = _clamp_window(mid - min_span / 2, mid + min_span / 2)
        self._on_view_changed(s, e)

    def _update_loop_zoom_button(self) -> None:
        a_sec, b_sec = self._engine.loop_bounds_seconds()
        can = self._loop_btn.isChecked() and b_sec > a_sec + 0.001
        self._zoom_bar.set_loop_zoom_enabled(can)

    def _on_bpm_detected(self, bpm: float) -> None:
        self._tempo_bar.set_bpm(bpm)
        dur = self._engine.duration
        num = self._tempo_bar._numerator
        den = self._tempo_bar._denominator
        self._overview.set_tempo(bpm, num, den, dur)
        self._detail.set_tempo(bpm, num, den, dur)

    def _on_tempo_changed(self, bpm: float, numerator: int, denominator: int) -> None:
        dur = self._engine.duration
        self._overview.set_tempo(bpm, numerator, denominator, dur)
        self._detail.set_tempo(bpm, numerator, denominator, dur)

    def closeEvent(self, event):
        if self._bpm_worker is not None and self._bpm_worker.isRunning():
            self._bpm_worker.quit()
            self._bpm_worker.wait(2000)  # wait up to 2s; librosa won't stop mid-run but guards the signal
        self._timer.stop()
        self._engine.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._on_play_pause()
        else:
            super().keyPressEvent(event)
