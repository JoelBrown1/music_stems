# Drum MIDI madmom Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the spectral-centroid drum classifier in `drum_midi.py` with madmom's `RNNDrumOnsetProcessor` neural network, adding velocity dynamics.

**Architecture:** `RNNDrumOnsetProcessor` processes the wav file and returns a `(n_frames, 3)` activation array (kick/snare/hi-hat columns). Each column is peak-picked independently with `scipy.signal.find_peaks` at `threshold = 1.0 - sensitivity`. Each peak's activation magnitude maps to MIDI velocity 40–127. The public function signature, UI parameter, and error message are all unchanged.

**Tech Stack:** madmom (new dep), scipy.signal.find_peaks (scipy already installed via librosa), pretty_midi (existing)

---

## File Map

| File | Action | What changes |
|---|---|---|
| `requirements.txt` | Modify | Add `madmom` |
| `stem_splitter/core/drum_midi.py` | Rewrite | Replace spectral centroid heuristic with madmom RNN pipeline |
| `tests/test_drum_midi.py` | Rewrite | Mock-based tests replacing the real-audio tests |

---

### Task 1: Install madmom and add to requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Install madmom in the venv**

```bash
.venv/bin/pip install madmom
```

Expected output ends with: `Successfully installed madmom-...`

If it fails with a Cython/compilation error, try:
```bash
.venv/bin/pip install madmom --no-build-isolation
```

- [ ] **Step 2: Verify the import works**

```bash
.venv/bin/python -c "from madmom.features.drums import RNNDrumOnsetProcessor; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Add madmom to requirements.txt**

Current `requirements.txt`:
```
PyQt6>=6.6.0
yt-dlp
demucs
basic-pitch
sounddevice
soundfile
numpy
librosa
pretty_midi
piano_transcription_inference
pytest
```

Add `madmom` after `librosa`:
```
PyQt6>=6.6.0
yt-dlp
demucs
basic-pitch
sounddevice
soundfile
numpy
librosa
madmom
pretty_midi
piano_transcription_inference
pytest
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add madmom dependency for drum MIDI transcription"
```

---

### Task 2: Replace drum engine with madmom (TDD)

**Files:**
- Rewrite: `stem_splitter/core/drum_midi.py`
- Rewrite: `tests/test_drum_midi.py`

- [ ] **Step 1: Write failing tests**

Replace the entire contents of `tests/test_drum_midi.py` with:

```python
import numpy as np
import pytest
import pretty_midi
from unittest.mock import patch
from stem_splitter.core.drum_midi import convert_drums_to_midi


def _activations(n_frames=300, kick_at=None, snare_at=None, hh_at=None,
                 kick_val=0.9, snare_val=0.8, hh_val=0.7):
    """Build a (n_frames, 3) activation array with isolated peaks."""
    act = np.zeros((n_frames, 3))
    if kick_at is not None:
        act[kick_at, 0] = kick_val
    if snare_at is not None:
        act[snare_at, 1] = snare_val
    if hh_at is not None:
        act[hh_at, 2] = hh_val
    return act


@patch("stem_splitter.core.drum_midi.RNNDrumOnsetProcessor")
def test_gm_note_routing(MockProc, tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    MockProc.return_value.return_value = _activations(kick_at=10, snare_at=100, hh_at=200)
    result = convert_drums_to_midi(wav, tmp_path, sensitivity=0.5)
    midi = pretty_midi.PrettyMIDI(str(result))
    pitches = {n.pitch for n in midi.instruments[0].notes}
    assert pitches == {36, 38, 42}


@patch("stem_splitter.core.drum_midi.RNNDrumOnsetProcessor")
def test_velocity_scales_with_activation(MockProc, tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    # activation 0.9 → velocity = int(40 + 0.9 * 87) = int(118.3) = 118
    MockProc.return_value.return_value = _activations(kick_at=10, kick_val=0.9)
    result = convert_drums_to_midi(wav, tmp_path, sensitivity=0.5)
    midi = pretty_midi.PrettyMIDI(str(result))
    kick_notes = [n for n in midi.instruments[0].notes if n.pitch == 36]
    assert len(kick_notes) == 1
    assert kick_notes[0].velocity == 118


@patch("stem_splitter.core.drum_midi.RNNDrumOnsetProcessor")
def test_sensitivity_filters_weak_peaks(MockProc, tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    # threshold = 1.0 - 0.5 = 0.5; peak at 0.9 survives, peak at 0.3 is filtered
    act = np.zeros((300, 3))
    act[10, 0] = 0.9
    act[100, 0] = 0.3
    MockProc.return_value.return_value = act
    result = convert_drums_to_midi(wav, tmp_path, sensitivity=0.5)
    midi = pretty_midi.PrettyMIDI(str(result))
    kick_notes = [n for n in midi.instruments[0].notes if n.pitch == 36]
    assert len(kick_notes) == 1


@patch("stem_splitter.core.drum_midi.RNNDrumOnsetProcessor")
def test_no_onsets_raises(MockProc, tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    MockProc.return_value.return_value = np.zeros((300, 3))
    with pytest.raises(RuntimeError, match="No drum hits detected"):
        convert_drums_to_midi(wav, tmp_path, sensitivity=0.5)


@patch("stem_splitter.core.drum_midi.RNNDrumOnsetProcessor")
def test_midi_output_is_valid_drum_track(MockProc, tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    MockProc.return_value.return_value = _activations(kick_at=10)
    result = convert_drums_to_midi(wav, tmp_path, sensitivity=0.5)
    assert result == tmp_path / "drums.mid"
    assert result.exists()
    midi = pretty_midi.PrettyMIDI(str(result))
    assert len(midi.instruments) == 1
    assert midi.instruments[0].is_drum is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_drum_midi.py -v
```

Expected: All 5 tests FAIL — `RNNDrumOnsetProcessor` is not yet imported in `drum_midi.py`, so the mock patch target doesn't exist.

- [ ] **Step 3: Rewrite drum_midi.py**

Replace the entire contents of `stem_splitter/core/drum_midi.py` with:

```python
import numpy as np
from pathlib import Path
from scipy.signal import find_peaks
import pretty_midi
from madmom.features.drums import RNNDrumOnsetProcessor

_DRUM_NOTES = [36, 38, 42]    # kick, snare, hi-hat — matches madmom column order
_FPS = 100                     # RNNDrumOnsetProcessor output frames per second
_NOTE_DURATION_SEC = 0.05
_VELOCITY_MIN = 40
_VELOCITY_MAX = 127


def convert_drums_to_midi(wav_path: Path, output_dir: Path, sensitivity: float = 0.50) -> Path:
    proc = RNNDrumOnsetProcessor()
    activations = proc(str(wav_path))   # (n_frames, 3) — columns: kick, snare, hi-hat

    threshold = 1.0 - sensitivity
    midi = pretty_midi.PrettyMIDI()
    drum_track = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    any_detections = False

    for col, gm_note in enumerate(_DRUM_NOTES):
        peak_indices, _ = find_peaks(activations[:, col], height=threshold)
        for idx in peak_indices:
            any_detections = True
            t = idx / _FPS
            raw = float(activations[idx, col])
            velocity = max(_VELOCITY_MIN, min(_VELOCITY_MAX,
                           int(_VELOCITY_MIN + raw * (_VELOCITY_MAX - _VELOCITY_MIN))))
            drum_track.notes.append(pretty_midi.Note(
                velocity=velocity, pitch=gm_note,
                start=t, end=t + _NOTE_DURATION_SEC,
            ))

    if not any_detections:
        raise RuntimeError("No drum hits detected — try lowering sensitivity")

    midi.instruments.append(drum_track)
    dest = output_dir / "drums.mid"
    midi.write(str(dest))
    return dest
```

- [ ] **Step 4: Run drum tests to verify they pass**

```bash
.venv/bin/pytest tests/test_drum_midi.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Run the full test suite**

```bash
.venv/bin/pytest -v
```

Expected: All tests pass. The change is self-contained to `drum_midi.py`.

- [ ] **Step 6: Commit**

```bash
git add stem_splitter/core/drum_midi.py tests/test_drum_midi.py
git commit -m "feat: replace spectral centroid drum classifier with madmom RNN engine"
```
