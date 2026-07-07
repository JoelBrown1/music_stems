# Zoomable Timeline with Loop Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single `ScrubberWidget` with a two-row timeline — a thin always-full-song overview strip and a taller zoomable detail timeline — so loop A/B points can be placed and refined precisely against the musical beat grid.

**Architecture:** All new classes live in `stem_splitter/ui/player_window.py` alongside the existing widgets. The feature rests on a layer of pure coordinate-transform helper functions (fully unit-tested), followed by three new QWidget subclasses (`OverviewStrip`, `DetailTimeline`, `ZoomControlBar`), then a wiring pass in `PlayerWindow` that removes `ScrubberWidget` and connects the new widgets.

**Tech Stack:** PyQt6 (QWidget, QPainter, QScrollBar, pyqtSignal), Python 3.11

## Global Constraints

- All code goes in `stem_splitter/ui/player_window.py` and `tests/test_player_window.py` only — no new files
- Test runner: `.venv/bin/python -m pytest tests/test_player_window.py -v`
- Minimum view window span: `1/64` of total song (constant `_MIN_SPAN = 1.0 / 64.0`)
- Wheel zoom step: factor `0.8` (zoom in) / `1.25` (zoom out)
- Button zoom step: factor `0.5` (zoom in) / `2.0` (zoom out), centered on view midpoint
- Auto-pan margin: `5%` of current view span (`_AUTO_PAN_MARGIN = 0.05`)
- Beat snap threshold: `10` screen pixels
- Snap modifier key: `Qt.KeyboardModifier.ControlModifier` (maps to ⌘ Command on macOS in Qt)
- Snapping indicator: active drag marker line drawn white instead of orange
- Overview strip fixed height: `24` px
- Detail timeline minimum height: `64` px
- `ScrubberWidget` is deleted entirely in Task 5 — it must not be referenced after that
- No changes to `PlayerEngine`, `TempoInfoBar`, `BpmDetectWorker`, `StretchWorker`, transport, speed control, or loop controls panel

---

### Task 1: Coordinate transform and zoom helper functions

**Files:**
- Modify: `stem_splitter/ui/player_window.py` — add 7 module-level pure functions after `_beat_fractions`
- Modify: `tests/test_player_window.py` — add 18 tests

**Interfaces:**
- Produces:
  - `_MIN_SPAN: float = 1.0 / 64.0`
  - `_to_screen(fraction, view_start, view_end, width) -> int`
  - `_to_fraction(x, view_start, view_end, width) -> float`
  - `_zoom_centered(view_start, view_end, factor, center) -> tuple[float, float]`
  - `_clamp_window(start, end) -> tuple[float, float]`
  - `_nearest_beat_fraction(fraction, bpm, duration) -> float`
  - `_should_snap(fraction, nearest, view_start, view_end, width, threshold_px=10) -> bool`

- [ ] **Step 1: Write 18 failing tests**

Add these tests to `tests/test_player_window.py`. Update the import at the top to include the new names:

```python
from stem_splitter.ui.player_window import (
    _measure_fractions, _beat_fractions,
    _to_screen, _to_fraction, _zoom_centered, _clamp_window,
    _nearest_beat_fraction, _should_snap, _MIN_SPAN,
)
```

Then add the test functions at the bottom of the file:

```python
# --- _to_screen ---

def test_to_screen_maps_zero():
    assert _to_screen(0.0, 0.0, 1.0, 800) == 0

def test_to_screen_maps_one():
    assert _to_screen(1.0, 0.0, 1.0, 800) == 800

def test_to_screen_maps_midpoint():
    assert _to_screen(0.5, 0.0, 1.0, 800) == 400

def test_to_screen_zoomed_left_edge():
    # view [0.25, 0.75]: fraction 0.25 → x=0
    assert _to_screen(0.25, 0.25, 0.75, 800) == 0

def test_to_screen_zoomed_right_edge():
    # view [0.25, 0.75]: fraction 0.75 → x=800
    assert _to_screen(0.75, 0.25, 0.75, 800) == 800

def test_to_screen_zoomed_midpoint():
    # view [0.25, 0.75]: fraction 0.5 → x=400
    assert _to_screen(0.5, 0.25, 0.75, 800) == 400

# --- _to_fraction ---

def test_to_fraction_maps_zero():
    assert _to_fraction(0.0, 0.0, 1.0, 800) == pytest.approx(0.0)

def test_to_fraction_maps_full_width():
    assert _to_fraction(800.0, 0.0, 1.0, 800) == pytest.approx(1.0)

def test_to_fraction_zoomed_left_edge():
    # view [0.25, 0.75]: x=0 → fraction 0.25
    assert _to_fraction(0.0, 0.25, 0.75, 800) == pytest.approx(0.25)

def test_to_fraction_zoomed_right_edge():
    # view [0.25, 0.75]: x=800 → fraction 0.75
    assert _to_fraction(800.0, 0.25, 0.75, 800) == pytest.approx(0.75)

# --- _zoom_centered ---

def test_zoom_centered_2x_around_center():
    # factor=0.5 (zoom in 2×) around 0.5 from full view
    s, e = _zoom_centered(0.0, 1.0, 0.5, 0.5)
    assert s == pytest.approx(0.25)
    assert e == pytest.approx(0.75)

def test_zoom_centered_zoom_out_to_full():
    # factor=2.0 (zoom out) from half-view centered at 0.5
    s, e = _zoom_centered(0.25, 0.75, 2.0, 0.5)
    assert s == pytest.approx(0.0)
    assert e == pytest.approx(1.0)

def test_zoom_centered_clamps_minimum_span():
    # Extreme zoom in must not produce span below _MIN_SPAN
    s, e = _zoom_centered(0.499, 0.501, 0.001, 0.5)
    assert (e - s) == pytest.approx(_MIN_SPAN)

def test_zoom_centered_stays_within_bounds():
    # Zooming near the left edge must not go negative
    s, e = _zoom_centered(0.0, 0.1, 0.5, 0.0)
    assert s >= 0.0
    assert e <= 1.0

# --- _clamp_window ---

def test_clamp_window_no_change():
    s, e = _clamp_window(0.2, 0.8)
    assert s == pytest.approx(0.2)
    assert e == pytest.approx(0.8)

def test_clamp_window_left_overflow():
    s, e = _clamp_window(-0.1, 0.4)
    assert s == pytest.approx(0.0)
    assert e == pytest.approx(0.5)

def test_clamp_window_right_overflow():
    s, e = _clamp_window(0.7, 1.1)
    assert e == pytest.approx(1.0)
    assert s == pytest.approx(0.6)

# --- _nearest_beat_fraction ---

def test_nearest_beat_fraction_on_beat():
    # 120 bpm, 60s song: beat at 0.5s = fraction 0.5/60
    beat_frac = 0.5 / 60.0
    assert _nearest_beat_fraction(beat_frac, 120.0, 60.0) == pytest.approx(beat_frac, abs=1e-6)

def test_nearest_beat_fraction_snaps_to_nearest():
    # 120 bpm, 60s song: beat at 1.0s = fraction 1/60; slightly off
    result = _nearest_beat_fraction(1.02 / 60.0, 120.0, 60.0)
    assert result == pytest.approx(1.0 / 60.0, abs=1e-4)

def test_nearest_beat_fraction_zero_bpm_returns_unchanged():
    assert _nearest_beat_fraction(0.5, 0.0, 60.0) == pytest.approx(0.5)

# --- _should_snap ---

def test_should_snap_within_threshold():
    # fraction and nearest 5px apart at 800px width → snap
    assert _should_snap(0.0, 5.0 / 800.0, 0.0, 1.0, 800) is True

def test_should_snap_outside_threshold():
    # fraction and nearest 15px apart → no snap
    assert _should_snap(0.0, 15.0 / 800.0, 0.0, 1.0, 800) is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_player_window.py -v
```

Expected: `ImportError` — `cannot import name '_to_screen'`

- [ ] **Step 3: Add the constant and helper functions to `player_window.py`**

Find `_beat_fractions` (around line 192 in the current file). Add the following block immediately after it, before `StretchWorker`:

```python
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
    """Scale the view window span by factor, keeping center fixed. Returns clamped (start, end)."""
    span = view_end - view_start
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
```

- [ ] **Step 4: Run tests to confirm all 21 tests pass**

```bash
.venv/bin/python -m pytest tests/test_player_window.py -v
```

Expected: 21 PASSED (13 existing + 3 beat-snap + the 18 new ones — adjust count based on current file)

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/ui/player_window.py tests/test_player_window.py
git commit -m "feat: add coordinate transform and zoom helper functions"
```

---

### Task 2: `OverviewStrip` widget

**Files:**
- Modify: `stem_splitter/ui/player_window.py` — add `OverviewStrip` class after the new helper functions from Task 1 and before `StretchWorker`

**Interfaces:**
- Consumes: `_measure_fractions`, `_beat_fractions`, `_MIN_SPAN` (Task 1)
- Produces:
  - `class OverviewStrip(QWidget)`
  - Signals: `seek_requested = pyqtSignal(float)`, `view_pan_requested = pyqtSignal(float)`
  - Methods: `set_position(fraction)`, `set_loop_start(fraction)`, `set_loop_end(fraction)`, `set_loop_enabled(enabled)`, `set_tempo(bpm, numerator, denominator, duration)`, `set_view_window(start, end)`

No unit tests for this widget (painting and mouse events require a live QApplication; correctness verified by running the app in Step 4).

- [ ] **Step 1: Add `OverviewStrip` to `player_window.py`**

Insert this class after the helper functions added in Task 1, before `StretchWorker`:

```python
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
```

- [ ] **Step 2: Run the existing tests to confirm nothing is broken**

```bash
.venv/bin/python -m pytest tests/test_player_window.py -v
```

Expected: all tests PASS (no new tests in this task)

- [ ] **Step 3: Run the app and visually verify**

```bash
.venv/bin/python -m stem_splitter.main
```

`OverviewStrip` is not yet wired into the UI — this step just confirms the module imports without error. If it crashes on import, check for syntax errors in the new class.

- [ ] **Step 4: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: add OverviewStrip always-full-song timeline widget"
```

---

### Task 3: `DetailTimeline` widget

**Files:**
- Modify: `stem_splitter/ui/player_window.py` — add `_DRAG_PAN = 4` to the drag constants at the top; add `DetailTimeline` class after `OverviewStrip`

**Interfaces:**
- Consumes: `_to_screen`, `_to_fraction`, `_zoom_centered`, `_clamp_window`, `_nearest_beat_fraction`, `_should_snap`, `_MIN_SPAN`, `_AUTO_PAN_MARGIN`, `_measure_fractions`, `_beat_fractions`, `_DRAG_NONE/PLAYHEAD/LOOP_A/LOOP_B`, `_HIT_RADIUS` (all from Tasks 1 and existing file)
- Produces:
  - `_DRAG_PAN: int = 4`
  - `class DetailTimeline(QWidget)`
  - Signals: `seek_requested = pyqtSignal(float)`, `loop_start_changed = pyqtSignal(float)`, `loop_end_changed = pyqtSignal(float)`, `zoom_changed = pyqtSignal(float, float)`
  - Methods: `set_position(fraction)`, `set_loop_start(fraction)`, `set_loop_end(fraction)`, `set_loop_enabled(enabled)`, `set_tempo(bpm, numerator, denominator, duration)`, `set_view_window(start, end)`

- [ ] **Step 1: Add `_DRAG_PAN = 4` to the drag constants block**

Find the existing constants at the top of `player_window.py`:

```python
_DRAG_NONE = 0
_DRAG_PLAYHEAD = 1
_DRAG_LOOP_A = 2
_DRAG_LOOP_B = 3
_HIT_RADIUS = 8
```

Add `_DRAG_PAN = 4` after `_DRAG_LOOP_B = 3`:

```python
_DRAG_NONE = 0
_DRAG_PLAYHEAD = 1
_DRAG_LOOP_A = 2
_DRAG_LOOP_B = 3
_DRAG_PAN = 4
_HIT_RADIUS = 8
```

- [ ] **Step 2: Add `DetailTimeline` class after `OverviewStrip`**

```python
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
```

- [ ] **Step 3: Run tests to confirm nothing is broken**

```bash
.venv/bin/python -m pytest tests/test_player_window.py -v
```

Expected: all tests PASS

- [ ] **Step 4: Confirm the module imports without error**

```bash
.venv/bin/python -c "from stem_splitter.ui.player_window import DetailTimeline; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: add DetailTimeline zoomable loop-editing widget"
```

---

### Task 4: `ZoomControlBar` widget

**Files:**
- Modify: `stem_splitter/ui/player_window.py` — add `ZoomControlBar` class after `DetailTimeline`, before `StretchWorker`

**Interfaces:**
- Consumes: `_zoom_centered`, `_clamp_window` (Task 1); `QScrollBar`, `QVBoxLayout`, `QHBoxLayout`, `QPushButton` (already imported at line ~161)
- Produces:
  - `class ZoomControlBar(QWidget)`
  - Signals: `zoom_changed = pyqtSignal(float, float)`, `reset_requested = pyqtSignal()`, `zoom_to_loop_requested = pyqtSignal()`
  - Methods: `set_view_window(start, end)`, `set_loop_zoom_enabled(enabled)`

- [ ] **Step 1: Check the imports block**

Around line 161–169 the file has:

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGroupBox, QLineEdit,
)
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
```

`QScrollBar` is not yet imported. Add it to the `QtWidgets` import:

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGroupBox, QLineEdit, QScrollBar,
)
```

- [ ] **Step 2: Add `ZoomControlBar` after `DetailTimeline`**

```python
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
```

- [ ] **Step 3: Run tests to confirm nothing is broken**

```bash
.venv/bin/python -m pytest tests/test_player_window.py -v
```

Expected: all tests PASS

- [ ] **Step 4: Confirm import**

```bash
.venv/bin/python -c "from stem_splitter.ui.player_window import ZoomControlBar; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: add ZoomControlBar with zoom buttons and scrollbar"
```

---

### Task 5: `PlayerWindow` wiring + retire `ScrubberWidget`

**Files:**
- Modify: `stem_splitter/ui/player_window.py` — rewrite `_build_scrubber_section`; update `_on_tick`, `_on_loop_toggle`, `_on_set_a`, `_on_set_b`, `_on_bpm_detected`, `_on_tempo_changed`; add `_on_view_changed`, `_on_overview_pan`, `_on_zoom_reset`, `_on_zoom_to_loop`, `_update_loop_zoom_button`; delete the `ScrubberWidget` class entirely

**Interfaces:**
- Consumes: `OverviewStrip`, `DetailTimeline`, `ZoomControlBar` (Tasks 2–4); `_clamp_window` (Task 1)
- No new public interface produced — this is wiring-only

- [ ] **Step 1: Delete `ScrubberWidget`**

Remove the entire `ScrubberWidget` class (lines 15–158 in the original file, though line numbers will have shifted after Tasks 1–4). It starts with `class ScrubberWidget(QWidget):` and ends just before the second imports block. Delete the whole class.

- [ ] **Step 2: Rewrite `_build_scrubber_section`**

Find the existing `_build_scrubber_section` method in `PlayerWindow` and replace it entirely:

```python
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
```

- [ ] **Step 3: Add new `PlayerWindow` helper methods**

Add these four methods to `PlayerWindow` (e.g. just before `_on_bpm_detected`):

```python
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
```

- [ ] **Step 4: Update `_on_tick`**

Replace the existing `_on_tick` method:

```python
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
```

- [ ] **Step 5: Update `_on_loop_toggle`**

Replace the existing `_on_loop_toggle` method:

```python
def _on_loop_toggle(self, checked: bool) -> None:
    self._engine.set_loop_enabled(checked)
    self._overview.set_loop_enabled(checked)
    self._detail.set_loop_enabled(checked)
    self._loop_btn.setStyleSheet(
        "color: #f39c12; border: 1px solid #f39c12;" if checked else ""
    )
    self._update_loop_zoom_button()
```

- [ ] **Step 6: Update `_on_set_a` and `_on_set_b`**

Replace both methods:

```python
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
```

- [ ] **Step 7: Update `_on_bpm_detected` and `_on_tempo_changed`**

Replace both methods:

```python
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
```

- [ ] **Step 8: Search for any remaining `self._scrubber` references and remove them**

```bash
grep -n '_scrubber' stem_splitter/ui/player_window.py
```

Expected: no output. If any remain, replace them with the equivalent calls to `self._overview` and `self._detail`.

- [ ] **Step 9: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_player_window.py -v
```

Expected: all tests PASS

- [ ] **Step 10: Run the app and verify the full feature**

```bash
.venv/bin/python -m stem_splitter.main
```

Open a track. Verify:
1. Two-row timeline appears (thin overview + taller detail)
2. Playhead moves in both strips while playing
3. Shaded box on overview tracks correctly
4. Mouse wheel on detail timeline zooms in/out
5. `+` / `−` buttons zoom in/out
6. Scrollbar appears when zoomed and pans correctly
7. `↺` resets to full view
8. Dragging the shaded box on overview pans the detail view
9. Set A and Set B, enable loop — orange region and A/B markers appear in both strips
10. Drag A or B handle in detail — marker moves, loop updates, overview reflects it
11. Drag A or B handle near the edge of detail view — view auto-pans to follow
12. Hold ⌘ while dragging A or B — marker snaps to nearest beat (turns white)
13. With loop set and loop enabled, `⊡ Zoom to loop` button becomes active; clicking it fits the loop region in the detail view
14. Playhead auto-follows in detail view while playing at any zoom level

- [ ] **Step 11: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: wire zoomable timeline into PlayerWindow, retire ScrubberWidget"
```
