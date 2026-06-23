# Tempo Ruler Design Spec

**Date:** 2026-06-22  
**Status:** Approved

## Summary

Display BPM, time signature, and measure markers above/through the scrubber in `PlayerWindow`. BPM is auto-detected via librosa when a track loads. Time signature is user-editable via double-click. Measure lines and beat dots are drawn through the scrubber bar itself (style B).

## Architecture

Two new classes added to `stem_splitter/ui/player_window.py`:

1. **`BpmDetectWorker(QThread)`** — detects BPM from audio in background, same pattern as existing `StretchWorker`
2. **`TempoInfoBar(QWidget)`** — horizontal info row showing BPM + time sig + elapsed time, with inline editing

`ScrubberWidget` gains a `set_tempo()` method and draws measure/beat markers in its existing `paintEvent`. No new files needed — all additions to `player_window.py`.

Four-layer architecture preserved: no core imports from UI.

## Components

### `BpmDetectWorker(QThread)`

```
Signals: detected(float)   # emits rounded BPM, or 0.0 on failure
```

- Receives the `PlayerEngine` reference at construction
- Builds a mono mix: sums all available stem numpy arrays, divides by count
- Calls `librosa.beat.beat_track(y=mono_mix, sr=engine.sample_rate)`
- Emits `detected(bpm)` — 0.0 if result is outside [40, 250] or on any exception
- Dispatched in `PlayerWindow.__init__` immediately after engine loads

### `TempoInfoBar(QWidget)`

```
Signals: tempo_changed(float, int, int)   # bpm, numerator, denominator
```

Layout (single horizontal row, left-aligned with stretch):
```
♩ [BPM label]    [numerator] / [denominator]    [elapsed / total]
```

**BPM label:**
- Starts as `"… BPM"`, updated by `BpmDetectWorker.detected` signal
- Double-click replaces with inline `QLineEdit`; Enter commits, Escape cancels
- Accepts integers 40–250; invalid input reverts silently

**Time signature:**
- `numerator` label (default `4`) and `denominator` label (default `4`)
- Double-click on either opens inline `QLineEdit` for that value
- Valid numerator: 1–16; valid denominator: 1, 2, 4, 8, 16
- Invalid input reverts silently
- On any change, emits `tempo_changed(bpm, numerator, denominator)`

**Time display:**
- Replaces the existing standalone `self._time_label` in `PlayerWindow`
- Updated by `PlayerWindow._on_tick` the same way as before

### `ScrubberWidget` changes

New method:
```python
def set_tempo(self, bpm: float, numerator: int, denominator: int, duration: float) -> None
```
Stores values and calls `self.update()`.

**`paintEvent` additions** (drawn after track/played region, before playhead):

- Skip all beat drawing if `bpm == 0` or `duration == 0`
- `seconds_per_beat = 60 / bpm`
- `seconds_per_measure = seconds_per_beat × numerator`
- For each measure boundary `t = 0, seconds_per_measure, 2×seconds_per_measure, …` while `t <= duration`:
  - `x = int((t / duration) * w)`
  - Draw vertical line: color `#7c83f580`, full height of scrubber bar
  - Draw measure number in 8px text just above bar: `#7c83f5` for measure 1, `#666666` for rest
- For each beat that is NOT a measure boundary:
  - Draw 3×3px filled circle, color `#444444`, centred vertically on bar
- Playhead drawn last (unchanged, always on top)

### `PlayerWindow` wiring

- `_build_scrubber_section` creates `TempoInfoBar` in place of the old `self._time_label`, subscribes to `tempo_changed`
- `__init__` creates and starts `BpmDetectWorker`; on `detected` signal, calls `self._tempo_bar.set_bpm(bpm)` and `self._scrubber.set_tempo(bpm, num, denom, self._engine.duration)`
- `_on_tick` calls `self._tempo_bar.update_time(elapsed, duration)` instead of setting `self._time_label` directly
- `_on_tempo_changed(bpm, num, denom)` slot: calls `self._scrubber.set_tempo(bpm, num, denom, self._engine.duration)`

## Error Handling

| Scenario | Behaviour |
|---|---|
| BPM detection fails / out of range | Shows `"? BPM"`, user can double-click to set manually |
| Invalid BPM entered by user | Reverts to previous value silently |
| Invalid time sig entered | Reverts to previous value silently |
| Track too short for any measure | Lines shown only where they fit; no crash |
| `librosa` not installed | `BpmDetectWorker` catches `ImportError`, emits `detected(0.0)` |

## Out of Scope

- Beat-snapping for the loop A/B markers
- Tempo map changes (BPM that changes mid-track)
- Visual metronome / click track playback
- Saving BPM/time sig between sessions
