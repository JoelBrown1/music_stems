# Drum MIDI — madmom Neural Network Engine Design Spec
**Date:** 2026-05-23
**Status:** Approved

## Overview

Replace the current spectral-centroid heuristic in `drum_midi.py` with madmom's `RNNDrumOnsetProcessor` — a recurrent neural network trained on multiple drum datasets that produces per-drum-type activation curves. This gives accurate kick/snare/hi-hat detection with velocity dynamics, without requiring a model download (madmom ships its weights inside the package).

**Goals:**
- Replace spectral centroid classification with a pre-trained RNN
- Add velocity dynamics (activation magnitude → MIDI velocity 40–127)
- Keep the existing public API, UI parameter (`sensitivity`), and error message unchanged

**Non-goals:**
- Detecting toms, crash, or ride cymbals (madmom's base model covers kick/snare/hi-hat)
- Per-drum-type sensitivity controls in the UI
- Training or fine-tuning the model

---

## Architecture

Change is entirely contained in `stem_splitter/core/drum_midi.py`. All other files — `MidiParams`, `MidiParamsWidget`, `midi.py` routing, `MidiWorker` — are unchanged.

**New dependency:** `madmom` (add to `requirements.txt`). No model download required; weights ship inside the package (~30 MB installed).

Public function signature is unchanged:

```python
def convert_drums_to_midi(wav_path: Path, output_dir: Path, sensitivity: float = 0.50) -> Path
```

---

## Pipeline

```
wav_path
  │
  ▼
RNNDrumOnsetProcessor          ← madmom RNN, CPU
  │
  │  activations: ndarray (n_frames, 3)
  │  columns: [kick, snare, hi-hat]
  ▼
Peak picking per column        ← threshold = 1.0 - sensitivity
  │                               high sensitivity → low threshold → more hits
  │  detections: list of (time_sec, peak_value) per drum type
  ▼
GM note mapping + velocity scaling
  │
  ▼
pretty_midi write → drums.mid
```

`RNNDrumOnsetProcessor` accepts the wav path directly and returns the activation array. Each column is peak-picked independently using `OnsetPeakPickingProcessor`. The activation magnitude at each peak becomes the note velocity.

---

## GM Note Mapping

| madmom column | GM note | Name |
|---|---|---|
| 0 — kick | 36 | Bass Drum 1 |
| 1 — snare | 38 | Acoustic Snare |
| 2 — hi-hat | 42 | Closed Hi-Hat |

If the installed madmom model distinguishes open vs. closed hi-hat (4 classes), open hi-hat maps to GM 46. This is an implementation detail to verify at build time.

---

## Sensitivity Mapping

`sensitivity` (0.10–0.90 from the UI slider) maps to madmom's peak-picking threshold as:

```
threshold = 1.0 - sensitivity
```

High sensitivity (0.90) → threshold 0.10 → more onsets detected.  
Low sensitivity (0.10) → threshold 0.90 → only the strongest hits detected.

---

## Velocity Scaling

```
velocity = clamp(int(40 + peak_activation * 87), 40, 127)
```

Peak activation 0.0 → velocity 40 (ppp). Peak activation 1.0 → velocity 127 (fff).

---

## Error Handling

| Failure | Behaviour |
|---|---|
| No onsets detected across all drum types | `RuntimeError("No drum hits detected — try lowering sensitivity")` |
| madmom processing error | Exception propagates to `MidiWorker`, shown as per-stem error in UI |

---

## Testing

`tests/test_drum_midi.py` is replaced with:

- **Routing test:** Mock `RNNDrumOnsetProcessor` to return a known activation matrix; assert GM pitches 36, 38, 42 appear in the output MIDI
- **Velocity scaling test:** Peak 0.0 → velocity 40; peak 1.0 → velocity 127; peak 0.5 → velocity ~84
- **Sensitivity mapping test:** `sensitivity=0.9` → threshold 0.1; `sensitivity=0.1` → threshold 0.9
- **No-onsets test:** All-zero activations → `RuntimeError` with expected message
- **MIDI validity test:** Output file exists, `is_drum=True`, notes on channel 9

---

## Technology Stack

| Component | Library | Notes |
|---|---|---|
| Drum onset detection + classification | madmom | New dependency; weights bundled (~30 MB) |
| MIDI output | pretty_midi | Existing |
| Audio loading | madmom (internal) | `RNNDrumOnsetProcessor` accepts wav path directly |
