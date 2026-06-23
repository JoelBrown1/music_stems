# Tempo Ruler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display auto-detected BPM, an editable time signature, and measure/beat markers drawn through the scrubber bar in `PlayerWindow`.

**Architecture:** All changes live in `stem_splitter/ui/player_window.py`. Two pure module-level helpers (`_measure_fractions`, `_beat_fractions`) feed `ScrubberWidget.set_tempo()`, which draws lines and dots in its existing `paintEvent`. A `BpmDetectWorker(QThread)` detects BPM from `PlayerEngine._arrays` in the background. A `TempoInfoBar(QWidget)` displays BPM + time sig + elapsed time with double-click inline editing. `PlayerWindow` wires everything together.

**Tech Stack:** PyQt6, librosa (already imported in `stem_splitter/core/player.py`), numpy, pytest

## Global Constraints

- PyQt6 only (no PyQt5, no PySide)
- All new code goes in `stem_splitter/ui/player_window.py` — no new files
- `from __future__ import annotations` already at top — do not add again
- `librosa` is a project dependency (already imported in `stem_splitter/core/player.py`)
- `PlayerEngine` attributes used: `_arrays: dict[str, np.ndarray]`, `_available: set[str]`, `_sample_rate: int`
- Tests go in `tests/test_player_window.py` (new file) — pure Python only, no Qt widget instantiation
- Test runner: `python3 -m pytest tests/test_player_window.py -v`
- Valid BPM range: 40–250 inclusive; `0.0` means "unknown/undetected"
- Valid time sig numerator: 1–16; valid denominator: 1, 2, 4, 8, or 16
- `_measure_fractions` and `_beat_fractions` are module-level functions (not methods) for testability
- Semi-transparent colors use `QColor('#rrggbb')` + `.setAlpha(n)` — never 8-digit hex strings (Qt parses those as AARRGGBB, not RRGGBBAA)

---

### Task 1: Beat grid helpers + `ScrubberWidget.set_tempo`

**Files:**
- Modify: `stem_splitter/ui/player_window.py`
- Create: `tests/test_player_window.py`

**Interfaces:**
- Produces:
  - `_measure_fractions(bpm: float, numerator: int, duration: float) -> list[tuple[float, int]]` — returns `(fraction, measure_number)` for each measure boundary; `fraction` in `[0.0, 1.0]`; `[]` if `bpm <= 0` or `duration <= 0`
  - `_beat_fractions(bpm: float, numerator: int, duration: float) -> list[float]` — fractions for non-measure-boundary beats; `[]` if `bpm <= 0` or `duration <= 0`
  - `ScrubberWidget.set_tempo(bpm: float, numerator: int, denominator: int, duration: float) -> None` — stores values, calls `self.update()`

- [ ] **Step 1: Write failing tests**

Create `tests/test_player_window.py`:

```python
# tests/test_player_window.py
from stem_splitter.ui.player_window import _measure_fractions, _beat_fractions


# --- _measure_fractions ---

def test_measure_fractions_zero_bpm_returns_empty():
    assert _measure_fractions(0.0, 4, 60.0) == []


def test_measure_fractions_zero_duration_returns_empty():
    assert _measure_fractions(120.0, 4, 0.0) == []


def test_measure_fractions_first_entry_is_zero_measure_one():
    result = _measure_fractions(120.0, 4, 10.0)
    assert result[0] == (0.0, 1)


def test_measure_fractions_120bpm_4_4_spacing():
    # 120 BPM, 4/4: seconds_per_beat=0.5, seconds_per_measure=2.0
    # In 10s: boundaries at t=0, 2, 4, 6, 8, 10 → fractions 0.0, 0.2, 0.4, 0.6, 0.8, 1.0
    result = _measure_fractions(120.0, 4, 10.0)
    fracs = [f for f, _ in result]
    assert abs(fracs[1] - 0.2) < 0.001
    assert abs(fracs[2] - 0.4) < 0.001


def test_measure_fractions_measure_numbers_increment():
    result = _measure_fractions(120.0, 4, 10.0)
    nums = [n for _, n in result]
    assert nums[0] == 1
    assert nums[1] == 2
    assert nums[2] == 3


def test_measure_fractions_3_4_time():
    # 120 BPM, 3/4: seconds_per_measure=1.5
    # In 6s: boundaries at t=0, 1.5, 3.0, 4.5, 6.0 → 5 entries
    result = _measure_fractions(120.0, 3, 6.0)
    assert len(result) == 5
    assert abs(result[1][0] - 0.25) < 0.001  # 1.5 / 6.0 = 0.25


def test_measure_fractions_no_fraction_above_one():
    result = _measure_fractions(60.0, 4, 3.0)
    # 60 BPM, 4/4: seconds_per_measure=4.0; only t=0 fits in 3s
    assert all(f <= 1.0 for f, _ in result)
    assert len(result) == 1


# --- _beat_fractions ---

def test_beat_fractions_zero_bpm_returns_empty():
    assert _beat_fractions(0.0, 4, 60.0) == []


def test_beat_fractions_zero_duration_returns_empty():
    assert _beat_fractions(120.0, 4, 0.0) == []


def test_beat_fractions_excludes_measure_boundaries():
    # 120 BPM, 4/4, 10s: measure boundaries at fractions 0.0, 0.2, 0.4, 0.6, 0.8, 1.0
    result = _beat_fractions(120.0, 4, 10.0)
    measure_fracs = {f for f, _ in _measure_fractions(120.0, 4, 10.0)}
    for frac in result:
        assert not any(abs(frac - mf) < 0.001 for mf in measure_fracs)


def test_beat_fractions_count_120bpm_4_4_10s():
    # 120 BPM, 4/4, 10s: 19 beats at t=0.5..9.5; 4 are measure boundaries (t=2,4,6,8)
    # Non-boundary count: 19 - 4 = 15
    result = _beat_fractions(120.0, 4, 10.0)
    assert len(result) == 15


def test_beat_fractions_all_within_zero_one():
    result = _beat_fractions(120.0, 4, 10.0)
    assert all(0.0 < f < 1.0 for f in result)


def test_beat_fractions_3_4_time():
    # 120 BPM, 3/4, 6s: beats at t=0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5
    # Measure boundaries: t=0,1.5,3.0,4.5,6.0 → beat_index%3==0: indices 3,6,9
    # Non-boundary: 11 total - 3 = 8
    result = _beat_fractions(120.0, 3, 6.0)
    assert len(result) == 8
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_player_window.py -v
```
Expected: `ImportError: cannot import name '_measure_fractions' from 'stem_splitter.ui.player_window'`

- [ ] **Step 3: Add `_measure_fractions` and `_beat_fractions` to `player_window.py`**

Add these two functions immediately after the `_fmt` function (around line 139):

```python
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
```

- [ ] **Step 4: Add tempo state to `ScrubberWidget.__init__` and `set_tempo` method**

In `ScrubberWidget.__init__`, after `self._drag: int = _DRAG_NONE`, add:

```python
self._bpm: float = 0.0
self._ts_numerator: int = 4
self._ts_denominator: int = 4
self._duration: float = 0.0
```

Add `set_tempo` method to `ScrubberWidget` (after `set_loop_enabled`):

```python
def set_tempo(self, bpm: float, numerator: int, denominator: int, duration: float) -> None:
    self._bpm = bpm
    self._ts_numerator = numerator
    self._ts_denominator = denominator
    self._duration = duration
    self.update()
```

- [ ] **Step 5: Add beat drawing to `ScrubberWidget.paintEvent`**

In `paintEvent`, add the following block AFTER the loop region block (ending with `painter.drawText(bx + 3, mid_y - 8, 'B')`) and BEFORE the white playhead block (`# White playhead`):

```python
# Measure lines and beat dots
if self._bpm > 0 and self._duration > 0:
    bar_y = mid_y - track_h // 2
    bar_h = track_h
    # Beat dots (non-measure boundaries)
    painter.setPen(Qt.PenStyle.NoPen)
    dot_color = QColor('#444444')
    painter.setBrush(dot_color)
    for frac in _beat_fractions(self._bpm, self._ts_numerator, self._duration):
        bx2 = int(frac * w)
        painter.drawEllipse(bx2 - 1, mid_y - 1, 3, 3)
    # Measure boundary lines and numbers
    small_font = painter.font()
    small_font.setPointSize(7)
    painter.setFont(small_font)
    for frac, measure_num in _measure_fractions(self._bpm, self._ts_numerator, self._duration):
        mx = int(frac * w)
        line_color = QColor('#7c83f5')
        line_color.setAlpha(0xb0 if measure_num == 1 else 0x60)
        painter.setPen(QPen(line_color, 1))
        painter.drawLine(mx, bar_y, mx, bar_y + bar_h)
        text_color = QColor('#7c83f5') if measure_num == 1 else QColor('#666666')
        painter.setPen(text_color)
        painter.drawText(mx + 2, bar_y - 2, str(measure_num))
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_player_window.py -v
```
Expected: all 14 tests PASS

- [ ] **Step 7: Commit**

```bash
git add stem_splitter/ui/player_window.py tests/test_player_window.py
git commit -m "feat: add beat grid helpers and ScrubberWidget.set_tempo with measure drawing"
```

---

### Task 2: `BpmDetectWorker`

**Files:**
- Modify: `stem_splitter/ui/player_window.py` (add class after `StretchWorker`)

**Interfaces:**
- Consumes: `PlayerEngine` (uses `._arrays`, `._available`, `._sample_rate`)
- Produces: `BpmDetectWorker(engine: PlayerEngine, parent=None)` with signal `detected = pyqtSignal(float)` — emits detected BPM (rounded integer as float), or `0.0` on failure or out-of-range [40, 250]

- [ ] **Step 1: Add `BpmDetectWorker` class after `StretchWorker`**

```python
class BpmDetectWorker(QThread):
    detected = pyqtSignal(float)

    def __init__(self, engine: PlayerEngine, parent=None):
        super().__init__(parent)
        self._engine = engine

    def run(self) -> None:
        try:
            import librosa
            import numpy as np
            arrays = self._engine._arrays
            available = self._engine._available
            sr = self._engine._sample_rate
            if not available or not arrays:
                self.detected.emit(0.0)
                return
            # Build mono mix: average left+right channels across all stems
            stems = [
                (arrays[s][:, 0] + arrays[s][:, 1]) * 0.5
                for s in available if s in arrays
            ]
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
```

- [ ] **Step 2: Run existing tests to confirm nothing broke**

```bash
python3 -m pytest tests/test_player_window.py -v
```
Expected: all 14 tests still PASS

- [ ] **Step 3: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: add BpmDetectWorker for background librosa beat detection"
```

---

### Task 3: `TempoInfoBar`

**Files:**
- Modify: `stem_splitter/ui/player_window.py` (add `_VALID_DENOMINATORS` constant + `TempoInfoBar` class before `PlayerWindow`)

**Interfaces:**
- Produces: `TempoInfoBar(parent=None)` with:
  - Signal: `tempo_changed = pyqtSignal(float, int, int)` — emits `(bpm, numerator, denominator)` on any user edit
  - `set_bpm(bpm: float) -> None` — updates BPM label; `bpm == 0.0` → shows `"? BPM"`
  - `update_time(elapsed: float, duration: float) -> None` — updates the time display
  - Internal state: `._bpm: float`, `._numerator: int`, `._denominator: int` (read by `PlayerWindow._on_bpm_detected`)

- [ ] **Step 1: Add `QLineEdit` to the existing `QtWidgets` import block**

The second import block (around line 125) currently reads:
```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGroupBox,
)
```

Change it to:
```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGroupBox, QLineEdit,
)
```

- [ ] **Step 2: Add `_VALID_DENOMINATORS` constant and `TempoInfoBar` class**

Add immediately before the `PlayerWindow` class:

```python
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
```

- [ ] **Step 3: Run existing tests**

```bash
python3 -m pytest tests/test_player_window.py -v
```
Expected: all 14 tests still PASS

- [ ] **Step 4: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: add TempoInfoBar with inline BPM and time signature editing"
```

---

### Task 4: `PlayerWindow` wiring

**Files:**
- Modify: `stem_splitter/ui/player_window.py` (`PlayerWindow.__init__`, `_build_scrubber_section`, `_on_tick`)

**Interfaces:**
- Consumes:
  - `BpmDetectWorker(engine, parent)` — `.detected` signal `pyqtSignal(float)`
  - `TempoInfoBar(parent)` — `.set_bpm(float)`, `.update_time(float, float)`, `.tempo_changed` signal, `._numerator: int`, `._denominator: int`
  - `ScrubberWidget.set_tempo(bpm: float, numerator: int, denominator: int, duration: float) -> None`

- [ ] **Step 1: Replace `_build_scrubber_section`**

Replace the entire `_build_scrubber_section` method:

```python
def _build_scrubber_section(self) -> QWidget:
    from PyQt6.QtWidgets import QWidget as _W, QVBoxLayout
    w = _W()
    col = QVBoxLayout(w)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(2)
    self._tempo_bar = TempoInfoBar()
    self._scrubber = ScrubberWidget()
    self._scrubber.seek_requested.connect(self._engine.seek)
    self._scrubber.loop_start_changed.connect(self._engine.set_loop_start)
    self._scrubber.loop_end_changed.connect(self._engine.set_loop_end)
    col.addWidget(self._tempo_bar)
    col.addWidget(self._scrubber)
    return w
```

- [ ] **Step 2: Add `_bpm_worker` to `__init__` and start `BpmDetectWorker`**

In `PlayerWindow.__init__`, after `self._stretch_worker: StretchWorker | None = None`, add:

```python
self._bpm_worker: BpmDetectWorker | None = None
```

After the last `layout.addWidget(...)` call (the speed control), add:

```python
self._tempo_bar.tempo_changed.connect(self._on_tempo_changed)
self._bpm_worker = BpmDetectWorker(self._engine, parent=self)
self._bpm_worker.detected.connect(self._on_bpm_detected)
self._bpm_worker.start()
```

- [ ] **Step 3: Add `_on_bpm_detected` and `_on_tempo_changed` slots to `PlayerWindow`**

Add these two methods (before `closeEvent`):

```python
def _on_bpm_detected(self, bpm: float) -> None:
    self._tempo_bar.set_bpm(bpm)
    self._scrubber.set_tempo(
        bpm,
        self._tempo_bar._numerator,
        self._tempo_bar._denominator,
        self._engine.duration,
    )

def _on_tempo_changed(self, bpm: float, numerator: int, denominator: int) -> None:
    self._scrubber.set_tempo(bpm, numerator, denominator, self._engine.duration)
```

- [ ] **Step 4: Update `_on_tick` to use `TempoInfoBar.update_time`**

In `_on_tick`, find and replace this line:

```python
self._time_label.setText(f"{_fmt(elapsed)} / {_fmt(dur)}")
```

With:

```python
self._tempo_bar.update_time(elapsed, dur)
```

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ --ignore=tests/test_recorder.py --ignore=tests/test_drum_midi.py --ignore=tests/test_piano_midi.py --ignore=tests/test_midi.py --ignore=tests/test_worker.py -v
```
Expected: all tests PASS including the 14 new ones in `test_player_window.py`

- [ ] **Step 6: Manual integration test**

```bash
.venv/bin/python -m stem_splitter.main
```

Open a track via File → Open Stems… or the Open Stems button. Verify:

1. Info bar shows `… BPM` immediately on open, then updates to a number (e.g. `120 BPM`) after ~2–3 seconds of BPM detection
2. Measure lines (semi-transparent purple vertical lines) appear through the scrubber bar
3. Small dark dots appear between measure lines (beat positions)
4. Measure numbers (1, 2, 3…) appear just above the bar at each line; measure 1 is brighter purple, others are grey
5. Double-clicking `120 BPM` opens an inline text field; typing `90` + Enter updates the label and redraws the ruler at 90 BPM
6. Double-clicking the numerator `4` and entering `3` switches to 3/4 time (fewer, wider measures)
7. Entering `0` for numerator or `300` for BPM silently reverts (no crash, no update)
8. The elapsed/total time still updates as the track plays
9. Loop markers, seek, and playhead all still work correctly

- [ ] **Step 7: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: wire TempoInfoBar and BpmDetectWorker into PlayerWindow"
```
