# Zoomable Timeline with Loop Editing Design Spec

**Date:** 2026-07-07
**Status:** Approved

## Summary

Replace the single `ScrubberWidget` with a two-row timeline: a thin always-full-song **overview strip** and a taller **zoomable detail timeline**. Loop A/B handles are draggable on both. The detail timeline zooms via mouse wheel or buttons, pans via scrollbar or drag, and auto-follows the playhead and dragged markers. Beat/measure lines from the tempo ruler spread apart as you zoom in, making precise loop editing against the musical grid natural.

## Layout

```
┌─────────────────────────────────────────────────────┐
│  TempoInfoBar (BPM / time sig / elapsed — unchanged) │
├─────────────────────────────────────────────────────┤
│  OverviewStrip  (24px tall, always full-song)        │
│  · playhead · loop A/B markers · measure lines       │
│  · shaded box showing current detail view window     │
├─────────────────────────────────────────────────────┤
│  DetailTimeline  (64px tall, zoomable)               │
│  · playhead · loop A/B markers · measure lines       │
│  · beat dots · draggable A/B handles                 │
├─────────────────────────────────────────────────────┤
│  [ − ]  zoom slider  [ + ]   [ ⊡ Zoom to loop ]  [↺] │
│  ←──────────── scrollbar ──────────────────────→    │
└─────────────────────────────────────────────────────┘
```

- The **overview strip** is always full-song. Clicking seeks; dragging the shaded box pans the detail view; clicking outside the box jumps the detail view to center on that point.
- The **detail timeline** is the main editing surface. All loop A/B dragging happens here (and is mirrored on the overview).
- The **control row** has zoom −/+ buttons, a zoom-to-loop button, a reset button, and a scrollbar that appears only when zoomed in.

## New Classes (all in `stem_splitter/ui/player_window.py`)

### `OverviewStrip(QWidget)`

Always renders the full song (no zoom state).

**Draws:** grey track, played region (purple), loop region (orange, semi-transparent), loop A/B markers with labels, measure lines (from tempo ruler), playhead (white circle), shaded view-window box (white, low alpha).

**Signals:**
- `seek_requested(float)` — fraction clicked/dragged
- `view_pan_requested(float)` — fraction to center the detail view on

**Public methods:**
- `set_position(fraction: float)`
- `set_loop_start(fraction: float)`
- `set_loop_end(fraction: float)`
- `set_loop_enabled(enabled: bool)`
- `set_tempo(bpm: float, numerator: int, denominator: int, duration: float)`
- `set_view_window(start: float, end: float)` — draws the shaded box

### `DetailTimeline(QWidget)`

The zoomable editing surface.

**Internal state:**
- `_view_start: float = 0.0` — left edge of visible window (song fraction)
- `_view_end: float = 1.0` — right edge of visible window (song fraction)
- `_drag: int` — which element is being dragged (none / playhead / loop A / loop B / pan)

**Coordinate transform** (used for all painting and hit-testing):
```python
def _to_screen(self, fraction: float) -> int:
    span = self._view_end - self._view_start
    return int((fraction - self._view_start) / span * self.width())

def _to_fraction(self, x: float) -> float:
    span = self._view_end - self._view_start
    return self._view_start + (x / self.width()) * span
```

**Draws:** same elements as current `ScrubberWidget` (track, played region, loop region, A/B markers, measure lines, beat dots, playhead), all transformed through the view window.

**Signals:**
- `seek_requested(float)`
- `loop_start_changed(float)`
- `loop_end_changed(float)`
- `zoom_changed(float, float)` — new `(view_start, view_end)` after any zoom/pan

**Public methods:**
- `set_position(fraction: float)` — also auto-pans if playhead leaves view
- `set_loop_start(fraction: float)`
- `set_loop_end(fraction: float)`
- `set_loop_enabled(enabled: bool)`
- `set_tempo(bpm: float, numerator: int, denominator: int, duration: float)`
- `set_view_window(start: float, end: float)` — called by `PlayerWindow` when zoom/pan changes

**Mouse interactions:**
- Wheel → zoom centered on cursor; emits `zoom_changed`
- Click/drag on playhead → seek
- Click/drag on A marker (loop enabled) → `loop_start_changed`; auto-pans if marker leaves view
- Click/drag on B marker (loop enabled) → `loop_end_changed`; auto-pans if marker leaves view
- Click/drag on empty area → pan; emits `zoom_changed`
- Hold ⌘ during A/B drag → snap to nearest beat

**Auto-pan rules:**
- While playing: when `set_position` is called and the new position is outside `[view_start, view_end]`, the view window shifts to keep the playhead centered
- While dragging A/B: if the marker moves within 5% of the view edge, the view pans at a rate proportional to how far past the edge the cursor is

### `ZoomControlBar(QWidget)`

**Contains:**
- `QPushButton("−")` — zoom out by 2×
- `QPushButton("+")` — zoom in by 2×
- `QPushButton("⊡ Zoom to loop")` — fit A→B into detail view with 10% margin each side; disabled when loop is off or A ≥ B
- `QPushButton("↺")` — reset to 1× (view_start=0.0, view_end=1.0)
- `QScrollBar(Horizontal)` — visible only when zoom > 1×; thumb width proportional to zoom level

**Signals:**
- `zoom_changed(float, float)` — new `(view_start, view_end)`
- `reset_requested()`

## `PlayerWindow` Wiring

`_build_scrubber_section()` replaces the old single `ScrubberWidget` with:

```python
self._overview = OverviewStrip()
self._detail = DetailTimeline()
self._zoom_bar = ZoomControlBar()

# Seek
self._overview.seek_requested.connect(self._engine.seek)
self._detail.seek_requested.connect(self._engine.seek)

# Loop editing
self._detail.loop_start_changed.connect(self._engine.set_loop_start)
self._detail.loop_end_changed.connect(self._engine.set_loop_end)

# View window sync (detail ↔ overview ↔ zoom bar)
self._detail.zoom_changed.connect(self._on_view_changed)
self._overview.view_pan_requested.connect(self._on_overview_pan)
self._zoom_bar.zoom_changed.connect(self._on_view_changed)
self._zoom_bar.reset_requested.connect(self._on_zoom_reset)
```

`_on_view_changed(start, end)` pushes the new window to all three widgets and updates the scrollbar thumb.

`_on_tick()` calls `set_position` on both `_overview` and `_detail` (replacing the old `_scrubber.set_position`). The detail's `set_position` handles playhead auto-pan internally.

Existing loop controls panel (`_build_loop_controls`, `_on_set_a`, `_on_set_b`, etc.) unchanged — they already talk to `_engine` and then push to the scrubber; they will push to `_overview` and `_detail` instead.

## Zoom Mechanics

- Zoom is stored as `(view_start, view_end)` — two song fractions
- Zoom level = `1.0 / (view_end - view_start)` (e.g. view 0.1→0.3 = 5× zoom)
- Minimum view window: `view_end - view_start ≥ 1/64` (about 2.8s on a 3-min track)
- Maximum view window: `view_end - view_start = 1.0` (1×, full song)
- Wheel zoom step: multiply span by 0.8 (zoom in) or 1.25 (zoom out), centered on cursor fraction
- Button zoom step: multiply span by 0.5 (zoom in) or 2.0 (zoom out), centered on current view midpoint
- View window always clamped to `[0.0, 1.0]`

## Beat Snapping

When ⌘ is held during A/B drag:
1. Compute the dragged fraction
2. Find the nearest beat time: `round(fraction * duration / seconds_per_beat) * seconds_per_beat / duration`
3. Snap only if the nearest beat is within 10px in screen coordinates
4. Flash the marker line white for one paint cycle to confirm the snap

No snap when BPM is 0 (not detected).

## Error Handling

| Scenario | Behavior |
|---|---|
| Zoom to loop when loop is disabled or A ≥ B | Button greyed out; no action |
| Loop region < 0.1s | Zoom to loop clamps view window to minimum 0.5s centered on the region |
| No detected BPM | Beat snapping is a no-op; drag stays free |
| Scrollbar dragged past song boundaries | View window clamped to `[0.0, 1.0]` |
| Window resized while zoomed | View window fractions preserved; pixel positions recomputed from new width |
| A/B marker dragged outside detail view | Detail view auto-pans to keep the dragged marker visible with a small margin |
| Playhead leaves detail view while playing | Detail view auto-pans to keep playhead centered |

## Out of Scope

- Beat-snapping for free playhead seeks (only A/B dragging snaps)
- Auto-follow toggle (always on; panning the view manually while playing is still possible)
- Waveform amplitude display (bars drawn from audio samples)
- Zoom memory per-track
- Keyboard shortcuts for zoom (beyond existing spacebar)
