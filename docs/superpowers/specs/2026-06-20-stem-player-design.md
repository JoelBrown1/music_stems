# Stem Player Design

**Date:** 2026-06-20
**Status:** Approved

## Overview

A floating `QDialog` player window that opens automatically when stem separation finishes. Plays all 6 separated stems simultaneously via a real-time sounddevice mixer, with per-stem volume, mute, and solo controls, a timeline scrubber with A–B loop markers, and time-stretch playback speed control.

## New Files

| File | Purpose |
|------|---------|
| `stem_splitter/core/player.py` | `PlayerEngine` — audio mixing logic, no Qt dependency |
| `stem_splitter/ui/player_window.py` | `PlayerWindow(QDialog)` — floating player UI |
| `tests/test_player.py` | Unit tests for `PlayerEngine` |

**Modified:** `stem_splitter/ui/main_window.py` — auto-open player in `_on_pipeline_finished`

## Architecture

### PlayerEngine (`core/player.py`)

Pure audio logic. No Qt imports. Owns the sounddevice stream and all stem audio data.

**Construction:** Receives `stem_paths: dict[str, Path]`. Loads each WAV via `soundfile.read()` into a numpy float32 array. If stems have mismatched sample rates, resamples to a common rate with `librosa.resample()`. Stores arrays in a dict keyed by stem name.

**Playback:** Opens a single `sounddevice.OutputStream`. The callback runs on the audio thread and for each chunk:
1. For each stem, slices the next N samples and multiplies by its volume scalar
2. Applies mute: substitutes zeros for muted stems
3. Applies solo: if any stem is soloed, zeros out all non-soloed stems
4. Sums all 6 arrays into a single stereo output buffer
5. Advances the position index by N samples
6. If loop is enabled and position has passed `loop_end_sample`, resets position to `loop_start_sample`

**Time-stretch:** `stretch(rate: float)` is a blocking call. Runs `librosa.effects.time_stretch(array, rate=rate)` on each stem array, replacing the in-memory arrays with the stretched versions. Resets position to the equivalent relative position in the new arrays. Called from a `QThread` in `PlayerWindow` — never called directly on the audio thread.

**Public API:**

```python
class PlayerEngine:
    def __init__(self, stem_paths: dict[str, Path]) -> None: ...

    def play(self) -> None: ...
    def pause(self) -> None: ...
    def stop(self) -> None: ...

    def seek(self, fraction: float) -> None: ...          # 0.0–1.0

    def set_volume(self, stem: str, value: float) -> None: ...  # 0.0–1.0
    def set_mute(self, stem: str, muted: bool) -> None: ...
    def set_solo(self, stem: str, soloed: bool) -> None: ...

    def set_loop_enabled(self, enabled: bool) -> None: ...
    def set_loop_start(self, fraction: float) -> None: ...
    def set_loop_end(self, fraction: float) -> None: ...

    def stretch(self, rate: float) -> None: ...           # blocking

    @property
    def position(self) -> float: ...    # 0.0–1.0, thread-safe read
    @property
    def duration(self) -> float: ...    # seconds
    @property
    def is_playing(self) -> bool: ...
```

`position` is read from the UI thread via a `QTimer` poll — it must be thread-safe (updated atomically with a lock or stored as a Python float, which is GIL-protected).

### PlayerWindow (`ui/player_window.py`)

`QDialog` subclass. Owns a `PlayerEngine` instance. Does not interact with `MainWindow` after opening — it is self-contained.

**Mixer strips:** One row per stem (order: vocals, drums, bass, guitar, piano, other), built from `core.output.STEMS`. Each row contains:
- Stem name label (fixed width)
- M button (`QPushButton`, checkable) — red border/text when active, calls `engine.set_mute()`
- S button (`QPushButton`, checkable) — green border/text when active, calls `engine.set_solo()`
- Volume `QSlider` (horizontal, 0–100) — calls `engine.set_volume()` on `valueChanged`
- Volume percentage label (updates with slider)

**Scrubber:** Custom `QWidget` subclass (`ScrubberWidget`). Paints:
- Grey track
- Blue played region (position 0 → playhead)
- Orange loop region (loop_start → loop_end, when loop enabled)
- White circular playhead (draggable)
- Orange A and B flag markers (draggable independently)

Mouse events:
- Click on track (not on a marker) → `engine.seek()`
- Drag playhead → `engine.seek()` continuously
- Drag A marker → `engine.set_loop_start()`
- Drag B marker → `engine.set_loop_end()`

Markers are only draggable when loop is enabled.

**Transport controls:**
- Play/Pause `QPushButton` (toggles label between ▶ Play and ⏸ Pause)
- Stop `QPushButton` — resets position to 0
- Time display: `0:32 / 3:47` (current / total), updated by timer

**Loop controls:**
- ⟳ Loop toggle button — orange when active, enables/disables loop and marker dragging
- Set A button — stamps `engine.position` as loop start, updates A marker
- Set B button — stamps `engine.position` as loop end, updates B marker
- Loop start/end time display (e.g. `A: 0:57  B: 2:16`)

**Speed control:**
- `QSlider` (25–100, step 5) with label showing current value (e.g. `75%`)
- Apply button — disabled while re-stretching
- On Apply: record current `is_playing` state, pause playback, disable Apply button, show "Processing…" label, start `StretchWorker(QThread)` that calls `engine.stretch(rate)`. On worker finished: hide label, re-enable Apply, restore previous playback state (resume only if was playing before Apply).

**`closeEvent`:** Calls `engine.stop()` to shut down the sounddevice stream before the window closes.

**`QTimer`** at 50ms interval:
- Reads `engine.position` and `engine.is_playing`
- Updates scrubber playhead position
- Updates time display
- Syncs Play/Pause button label to playback state

### MainWindow integration

In `_on_pipeline_finished`:

```python
def _on_pipeline_finished(self, output_dir: Path):
    self._set_pipeline_running(False)
    self._progress.reset()
    self._output.show_results(output_dir)
    if self._player is not None:
        self._player.close()
    self._player = PlayerWindow(output_dir, parent=self)
    self._player.show()
```

`self._player: PlayerWindow | None = None` added to `__init__`.

`PlayerWindow.__init__` receives `output_dir: Path` and derives stem paths as `{stem: output_dir / f"{stem}.wav" for stem in STEMS}`.

On window open, `PlayerWindow` positions itself to the right of `MainWindow` using `self.move(parent.geometry().right() + 8, parent.geometry().top())`.

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Stem WAV missing at player open | That stem's strip is greyed out and all controls disabled |
| No audio output device available | Transport controls hidden; inline error label shown: "No audio output device found" |
| Seek while paused | Position updates, scrubber moves, playback does not start |
| Set B before A chronologically | Swap silently so loop_start < loop_end |
| stretch() called with rate=1.0 | Skip processing, no-op |

## Testing

`tests/test_player.py` covers `PlayerEngine` with mocked `sounddevice.OutputStream`:

- Volume scaling: output buffer for a stem at 50% volume is half the input amplitude
- Mute: muted stem contributes zero samples regardless of volume setting
- Solo: non-soloed stems contribute zero samples when any stem is soloed
- Solo + mute interaction: muted stem that is also soloed outputs silence
- Loop wraparound: position resets to loop_start when it passes loop_end
- Loop disabled: position advances past loop_end without reset
- `stretch()`: output arrays have correct length for given rate (e.g. rate=0.5 → 2× length)
- `position` property: returns correct fraction after seek and after N samples of playback
- Missing stem file: constructor marks stem as unavailable without raising

`PlayerWindow` has no unit tests. Qt widget behaviour is verified manually.
