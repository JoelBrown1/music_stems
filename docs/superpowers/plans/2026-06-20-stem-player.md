# Stem Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a floating player window that opens automatically after stem separation, mixing all 6 stems in real-time with per-stem volume, mute, solo, A–B loop, and time-stretch controls.

**Architecture:** `PlayerEngine` (pure audio, no Qt) mixes stems in a `sounddevice.OutputStream` callback. `PlayerWindow` (QDialog) owns the engine and polls it via a 50ms QTimer. `MainWindow` creates and shows a new `PlayerWindow` whenever separation finishes.

**Tech Stack:** PyQt6, sounddevice, soundfile, numpy, librosa (all already in requirements.txt)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `stem_splitter/core/player.py` | `PlayerEngine` — all audio logic, zero Qt |
| Create | `stem_splitter/ui/player_window.py` | `PlayerWindow`, `ScrubberWidget`, `StretchWorker` |
| Create | `tests/test_player.py` | Unit tests for `PlayerEngine` only |
| Modify | `stem_splitter/ui/main_window.py` | Auto-open player in `_on_pipeline_finished` |

---

## Task 1: PlayerEngine — stem loading

**Files:**
- Create: `stem_splitter/core/player.py`
- Create: `tests/test_player.py`

- [ ] **Step 1: Write failing tests for stem loading**

```python
# tests/test_player.py
import numpy as np
import pytest
import soundfile as sf
from pathlib import Path
from stem_splitter.core.player import PlayerEngine


def _wav(path: Path, samples: int = 1000, sr: int = 44100) -> None:
    """Write a simple stereo WAV file of ones."""
    sf.write(str(path), np.ones((samples, 2), dtype='float32'), sr)


def test_loads_available_stems(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    _wav(tmp_path / 'drums.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav',
                           'drums': tmp_path / 'drums.wav'})
    assert engine._available == {'vocals', 'drums'}


def test_missing_stem_does_not_raise(tmp_path):
    _wav(tmp_path / 'drums.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'missing.wav',
                           'drums': tmp_path / 'drums.wav'})
    assert 'drums' in engine._available
    assert 'vocals' not in engine._available


def test_duration_matches_wav_length(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)  # exactly 1 second
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    assert abs(engine.duration - 1.0) < 0.01


def test_initial_position_is_zero(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    assert engine.position == 0.0


def test_initial_is_playing_false(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    assert engine.is_playing is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_player.py -v
```
Expected: `ModuleNotFoundError: No module named 'stem_splitter.core.player'`

- [ ] **Step 3: Implement PlayerEngine skeleton and stem loading**

```python
# stem_splitter/core/player.py
import threading
import numpy as np
import soundfile as sf
import librosa
import sounddevice as sd
from pathlib import Path


class PlayerEngine:
    def __init__(self, stem_paths: dict[str, Path]) -> None:
        self._lock = threading.Lock()
        self._arrays: dict[str, np.ndarray] = {}
        self._available: set[str] = set()
        self._sample_rate: int = 44100
        self._length: int = 0
        self._position: int = 0
        self._is_playing: bool = False
        self._stream: sd.OutputStream | None = None

        self._volumes: dict[str, float] = {}
        self._mutes: dict[str, bool] = {}
        self._solos: dict[str, bool] = {}
        self._loop_enabled: bool = False
        self._loop_start: int = 0
        self._loop_end: int = 0

        self._load_stems(stem_paths)

    def _load_stems(self, stem_paths: dict[str, Path]) -> None:
        raw: dict[str, tuple[np.ndarray, int]] = {}
        for stem, path in stem_paths.items():
            if not path.exists():
                continue
            data, sr = sf.read(str(path), dtype='float32', always_2d=True)
            raw[stem] = (data, sr)
            self._available.add(stem)

        if not raw:
            return

        target_sr = next(iter(raw.values()))[1]
        self._sample_rate = target_sr

        for stem, (data, sr) in raw.items():
            if sr != target_sr:
                resampled = np.stack([
                    librosa.resample(data[:, ch], orig_sr=sr, target_sr=target_sr)
                    for ch in range(data.shape[1])
                ], axis=1).astype('float32')
                self._arrays[stem] = resampled
            else:
                self._arrays[stem] = data
            self._volumes[stem] = 1.0
            self._mutes[stem] = False
            self._solos[stem] = False

        self._length = max(a.shape[0] for a in self._arrays.values())
        self._loop_end = self._length

    @property
    def position(self) -> float:
        with self._lock:
            return self._position / self._length if self._length > 0 else 0.0

    @property
    def duration(self) -> float:
        return self._length / self._sample_rate if self._sample_rate > 0 else 0.0

    @property
    def is_playing(self) -> bool:
        return self._is_playing
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_player.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/player.py tests/test_player.py
git commit -m "feat: add PlayerEngine skeleton with stem loading"
```

---

## Task 2: PlayerEngine — mixing (volume, mute, solo)

**Files:**
- Modify: `stem_splitter/core/player.py`
- Modify: `tests/test_player.py`

- [ ] **Step 1: Write failing tests for _mix_chunk**

Add these tests to `tests/test_player.py`:

```python
def test_volume_scaling(tmp_path):
    data = np.ones((1000, 2), dtype='float32')
    sf.write(str(tmp_path / 'vocals.wav'), data, 44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_volume('vocals', 0.5)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    np.testing.assert_allclose(outdata, 0.5)


def test_mute_produces_silence(tmp_path):
    data = np.ones((1000, 2), dtype='float32')
    sf.write(str(tmp_path / 'vocals.wav'), data, 44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_mute('vocals', True)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    np.testing.assert_allclose(outdata, 0.0)


def test_solo_silences_other_stems(tmp_path):
    for stem in ('vocals', 'drums'):
        sf.write(str(tmp_path / f'{stem}.wav'),
                 np.ones((1000, 2), dtype='float32'), 44100)
    engine = PlayerEngine({
        'vocals': tmp_path / 'vocals.wav',
        'drums': tmp_path / 'drums.wav',
    })
    engine.set_solo('vocals', True)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    # only vocals contributes — result is 1.0, not 2.0
    np.testing.assert_allclose(outdata, 1.0)


def test_muted_solo_produces_silence(tmp_path):
    data = np.ones((1000, 2), dtype='float32')
    sf.write(str(tmp_path / 'vocals.wav'), data, 44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_solo('vocals', True)
    engine.set_mute('vocals', True)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    np.testing.assert_allclose(outdata, 0.0)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_player.py::test_volume_scaling -v
```
Expected: `AttributeError: 'PlayerEngine' object has no attribute 'set_volume'`

- [ ] **Step 3: Implement set_volume, set_mute, set_solo, and _mix_chunk**

Add to `PlayerEngine` in `stem_splitter/core/player.py`:

```python
    def set_volume(self, stem: str, value: float) -> None:
        self._volumes[stem] = max(0.0, min(1.0, value))

    def set_mute(self, stem: str, muted: bool) -> None:
        self._mutes[stem] = muted

    def set_solo(self, stem: str, soloed: bool) -> None:
        self._solos[stem] = soloed

    def _mix_chunk(self, outdata: np.ndarray, frames: int) -> None:
        outdata[:] = 0.0

        with self._lock:
            arrays = self._arrays
            pos = self._position
            loop_enabled = self._loop_enabled
            loop_start = self._loop_start
            loop_end = self._loop_end
            total_len = self._length

        any_solo = any(self._solos.values())

        for stem, arr in arrays.items():
            if self._mutes.get(stem, False):
                continue
            if any_solo and not self._solos.get(stem, False):
                continue
            end = min(pos + frames, arr.shape[0])
            if end <= pos:
                continue
            chunk = arr[pos:end] * self._volumes.get(stem, 1.0)
            outdata[:chunk.shape[0]] += chunk

        with self._lock:
            new_pos = pos + frames
            if loop_enabled and loop_end > loop_start and new_pos >= loop_end:
                new_pos = loop_start
            elif not loop_enabled and new_pos >= total_len:
                new_pos = total_len
                self._is_playing = False
            self._position = new_pos
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/test_player.py -v
```
Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/player.py tests/test_player.py
git commit -m "feat: add PlayerEngine mixing with volume, mute, solo"
```

---

## Task 3: PlayerEngine — playback controls and position

**Files:**
- Modify: `stem_splitter/core/player.py`
- Modify: `tests/test_player.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_player.py`:

```python
def test_seek_updates_position(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(0.5)
    assert abs(engine.position - 0.5) < 0.001


def test_seek_clamps_to_valid_range(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(2.0)
    assert engine.position == 1.0
    engine.seek(-1.0)
    assert engine.position == 0.0


def test_mix_chunk_advances_position(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    outdata = np.zeros((512, 2), dtype='float32')
    engine._mix_chunk(outdata, 512)
    expected = 512 / 44100
    assert abs(engine.position - expected) < 0.001


def test_stop_resets_position(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(0.5)
    engine.stop()
    assert engine.position == 0.0
    assert engine.is_playing is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_player.py::test_seek_updates_position -v
```
Expected: `AttributeError: 'PlayerEngine' object has no attribute 'seek'`

- [ ] **Step 3: Implement play, pause, stop, seek**

Add to `PlayerEngine` in `stem_splitter/core/player.py`:

```python
    def play(self) -> None:
        if self._is_playing or not self._arrays:
            return

        def _callback(outdata, frames, time, status):
            self._mix_chunk(outdata, frames)
            if not self._is_playing:
                raise sd.CallbackStop()

        self._is_playing = True
        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=2,
            dtype='float32',
            callback=_callback,
        )
        self._stream.start()

    def pause(self) -> None:
        self._is_playing = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def stop(self) -> None:
        self._is_playing = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            self._position = 0

    def seek(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        with self._lock:
            self._position = int(fraction * self._length)
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/test_player.py -v
```
Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/player.py tests/test_player.py
git commit -m "feat: add PlayerEngine playback controls (play/pause/stop/seek)"
```

---

## Task 4: PlayerEngine — A–B loop

**Files:**
- Modify: `stem_splitter/core/player.py`
- Modify: `tests/test_player.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_player.py`:

```python
def test_loop_wraps_position_at_loop_end(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_loop_start(0.1)
    engine.set_loop_end(0.2)
    engine.set_loop_enabled(True)

    # seek just before loop end
    loop_end_sample = int(0.2 * 44100)
    engine.seek((loop_end_sample - 10) / 44100)

    outdata = np.zeros((512, 2), dtype='float32')
    engine._mix_chunk(outdata, 512)

    # position should have wrapped back to loop_start
    assert engine.position < 0.2
    assert engine.position >= 0.1


def test_loop_disabled_does_not_wrap(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_loop_start(0.1)
    engine.set_loop_end(0.2)
    engine.set_loop_enabled(False)

    engine.seek(0.19)
    outdata = np.zeros((512, 2), dtype='float32')
    engine._mix_chunk(outdata, 512)
    assert engine.position > 0.2


def test_set_loop_swaps_if_start_greater_than_end(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_loop_start(0.8)
    engine.set_loop_end(0.2)
    with engine._lock:
        assert engine._loop_start < engine._loop_end
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_player.py::test_loop_wraps_position_at_loop_end -v
```
Expected: `AttributeError: 'PlayerEngine' object has no attribute 'set_loop_start'`

- [ ] **Step 3: Implement loop controls**

Add to `PlayerEngine` in `stem_splitter/core/player.py`:

```python
    def set_loop_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._loop_enabled = enabled

    def set_loop_start(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        with self._lock:
            start = int(fraction * self._length)
            end = self._loop_end
            if start >= end:
                start, end = end, start
            self._loop_start = start
            self._loop_end = end

    def set_loop_end(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        with self._lock:
            end = int(fraction * self._length)
            start = self._loop_start
            if end <= start:
                start, end = end, start
            self._loop_start = start
            self._loop_end = end
```

Note: `_mix_chunk` already handles loop wraparound (implemented in Task 2). No changes needed there.

- [ ] **Step 4: Run all tests**

```bash
pytest tests/test_player.py -v
```
Expected: all 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/player.py tests/test_player.py
git commit -m "feat: add PlayerEngine A-B loop controls"
```

---

## Task 5: PlayerEngine — time-stretch

**Files:**
- Modify: `stem_splitter/core/player.py`
- Modify: `tests/test_player.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_player.py`:

```python
def test_stretch_halves_rate_doubles_length(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    original_len = engine._length
    engine.stretch(0.5)
    # half speed = double length (within 5% tolerance for phase vocoder)
    assert abs(engine._length - original_len * 2) < original_len * 0.05


def test_stretch_preserves_relative_position(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(0.5)
    engine.stretch(0.5)
    assert abs(engine.position - 0.5) < 0.01


def test_stretch_rate_1_is_noop(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    original_arrays = engine._arrays.copy()
    engine.stretch(1.0)
    assert engine._arrays is original_arrays  # same dict object, no-op
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_player.py::test_stretch_halves_rate_doubles_length -v
```
Expected: `AttributeError: 'PlayerEngine' object has no attribute 'stretch'`

- [ ] **Step 3: Implement stretch()**

Add to `PlayerEngine` in `stem_splitter/core/player.py`:

```python
    def stretch(self, rate: float) -> None:
        if rate == 1.0:
            return

        with self._lock:
            current_arrays = dict(self._arrays)
            old_length = self._length
            old_pos = self._position
            old_loop_start = self._loop_start
            old_loop_end = self._loop_end

        new_arrays: dict[str, np.ndarray] = {}
        for stem, arr in current_arrays.items():
            channels = [
                librosa.effects.time_stretch(arr[:, ch], rate=rate)
                for ch in range(arr.shape[1])
            ]
            new_arrays[stem] = np.stack(channels, axis=1).astype('float32')

        new_length = max(a.shape[0] for a in new_arrays.values()) if new_arrays else 0
        scale = new_length / old_length if old_length > 0 else 1.0

        with self._lock:
            self._arrays = new_arrays
            self._length = new_length
            self._position = int(old_pos * scale)
            self._loop_start = int(old_loop_start * scale)
            self._loop_end = int(old_loop_end * scale)
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/test_player.py -v
```
Expected: all 19 tests PASS

Note: the stretch tests process real audio with librosa and will take 5–10 seconds. This is expected.

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/player.py tests/test_player.py
git commit -m "feat: add PlayerEngine time-stretch via librosa phase vocoder"
```

---

## Task 6: ScrubberWidget

**Files:**
- Create: `stem_splitter/ui/player_window.py` (initial, ScrubberWidget only)

No unit tests — custom paint and mouse event behaviour is verified manually.

- [ ] **Step 1: Implement ScrubberWidget**

```python
# stem_splitter/ui/player_window.py
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
```

- [ ] **Step 2: Verify the file parses without errors**

```bash
python -c "from stem_splitter.ui.player_window import ScrubberWidget; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: add ScrubberWidget with draggable playhead and A-B loop markers"
```

---

## Task 7: PlayerWindow

**Files:**
- Modify: `stem_splitter/ui/player_window.py`

No unit tests — Qt widget behaviour verified manually by running the app.

- [ ] **Step 1: Implement StretchWorker and PlayerWindow**

Append to `stem_splitter/ui/player_window.py` after `ScrubberWidget`:

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGroupBox,
)
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from pathlib import Path
from stem_splitter.core.output import STEMS
from stem_splitter.core.player import PlayerEngine


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
            available = stem in self._engine._available

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
            self._engine.play()

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
        with self._engine._lock:
            a_sec = self._engine._loop_start / self._engine._sample_rate
            b_sec = self._engine._loop_end / self._engine._sample_rate
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
            self._engine.play()

    def _on_tick(self) -> None:
        pos = self._engine.position
        self._scrubber.set_position(pos)
        elapsed = pos * self._engine.duration
        self._time_label.setText(f"{_fmt(elapsed)} / {_fmt(self._engine.duration)}")
        self._play_btn.setText('⏸ Pause' if self._engine.is_playing else '▶ Play')

    def closeEvent(self, event):
        self._timer.stop()
        self._engine.stop()
        super().closeEvent(event)
```

- [ ] **Step 2: Add no-audio-device error handling to _on_play_pause**

Replace `_on_play_pause` in `PlayerWindow`:

```python
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
```

Also add `import sounddevice as sd` to the top-level imports in `player_window.py` (alongside the existing imports).

- [ ] **Step 3: Verify the file parses without import errors**

```bash
python -c "from stem_splitter.ui.player_window import PlayerWindow; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Run existing tests to confirm nothing broke**

```bash
pytest tests/test_player.py -v
```
Expected: all 19 tests PASS

- [ ] **Step 4: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: add PlayerWindow with mixer strips, scrubber, loop, and speed control"
```

---

## Task 8: MainWindow integration

**Files:**
- Modify: `stem_splitter/ui/main_window.py`

- [ ] **Step 1: Update MainWindow to open PlayerWindow after separation**

Edit `stem_splitter/ui/main_window.py`:

```python
from pathlib import Path
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QMessageBox
from stem_splitter.ui.source_panel import SourcePanel
from stem_splitter.ui.progress_panel import ProgressPanel
from stem_splitter.ui.output_panel import OutputPanel
from stem_splitter.ui.player_window import PlayerWindow      # ← new import
from stem_splitter.core.worker import PipelineWorker, MidiWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stem Splitter")
        self.setMinimumWidth(600)
        self._worker: PipelineWorker | None = None
        self._midi_worker: MidiWorker | None = None
        self._player: PlayerWindow | None = None             # ← new field

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._source = SourcePanel()
        self._progress = ProgressPanel()
        self._output = OutputPanel()

        layout.addWidget(self._source)
        layout.addWidget(self._progress)
        layout.addWidget(self._output)

        self._source.start_pipeline.connect(self._on_start_pipeline)
        self._output.convert_midi_requested.connect(self._on_convert_midi)

    def _set_pipeline_running(self, running: bool):
        self._source.setEnabled(not running)

    def _on_start_pipeline(self, source: str, track_name: str, is_url: bool):
        self._set_pipeline_running(True)
        self._output.setVisible(False)
        if is_url:
            self._progress.show_download()
        else:
            self._progress.show_separate()
        self._worker = PipelineWorker(source, track_name, is_url)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_pipeline_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, stage: str, value: int):
        if stage == "Separating":
            self._progress.show_separate()
        self._progress.update_progress(stage, value)

    def _on_pipeline_finished(self, output_dir: Path):
        self._set_pipeline_running(False)
        self._progress.reset()
        self._output.show_results(output_dir)
        if self._player is not None:                         # ← new
            self._player.close()                             # ← new
        self._player = PlayerWindow(output_dir, parent=self) # ← new
        self._player.show()                                  # ← new

    def _on_convert_midi(self, stems: list):
        if not stems:
            return
        output_dir = stems[0]["wav_path"].parent
        self._progress.show_midi()
        self._midi_worker = MidiWorker(stems, output_dir)
        self._midi_worker.progress.connect(
            lambda stem, pct: self._progress.update_progress(stem, pct)
        )
        self._midi_worker.finished.connect(self._progress.reset)
        self._midi_worker.error.connect(
            lambda stem, msg: QMessageBox.warning(
                self, "MIDI Error", f"Failed to convert {stem}: {msg}"
            )
        )
        self._midi_worker.start()

    def _on_error(self, message: str):
        self._set_pipeline_running(False)
        self._progress.reset()
        if self._output._output_dir is not None:
            self._output.setVisible(True)
        QMessageBox.critical(self, "Error", message)
```

- [ ] **Step 2: Run all tests**

```bash
pytest -v
```
Expected: all tests PASS

- [ ] **Step 3: Manually verify the player opens**

```bash
python -m stem_splitter.main
```

1. Load a local audio file (use any MP3/WAV — try one of the stems in `mom2TLs3Fi0/` like `vocals.wav`)
2. Confirm the Stem Player window opens automatically to the right of the main window after separation
3. Press ▶ Play — confirm audio plays
4. Drag a volume slider — confirm that stem gets louder/quieter in real-time
5. Press M on a stem — confirm it goes silent (red M)
6. Press S on a stem — confirm all others go silent (green S)
7. Click ⟳ Loop, drag scrubber A and B markers to set a loop region, press Play — confirm it loops
8. Set A and B using the Set A / Set B buttons while playing — confirm markers update
9. Drag the speed slider to 75%, click Apply — confirm "Processing…" appears briefly and playback resumes slower
10. Close the player, run another track — confirm a fresh player opens

- [ ] **Step 4: Commit**

```bash
git add stem_splitter/ui/main_window.py
git commit -m "feat: auto-open PlayerWindow when stem separation completes"
```
