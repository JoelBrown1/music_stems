# MIDI Conversion Upgrade — Design Spec
**Date:** 2026-05-23
**Status:** Approved

## Overview

Upgrade the Stem Splitter's MIDI conversion from a single Basic Pitch pass with no user controls to a three-engine system with per-stem parameter presets. Drums get a dedicated onset-detection engine; piano gets a specialized transcription model; all other pitched stems use Basic Pitch with exposed, per-stem tunable parameters.

**Goals:**
- Improve MIDI quality for all six stems
- Give users control over conversion parameters without requiring audio engineering knowledge
- Route each stem to the engine best suited to its characteristics automatically

**Non-goals:**
- User-saveable custom presets (presets are fixed constants in code)
- Cloud or server-based transcription
- MIDI editing within the app

---

## Architecture

Four core modules handle conversion; the UI never selects an engine directly.

```
stem_splitter/
├── core/
│   ├── midi_params.py    # MidiParams dataclass + per-stem DEFAULTS dict
│   ├── drum_midi.py      # librosa onset detection → pretty_midi GM MIDI
│   ├── piano_midi.py     # piano_transcription_inference wrapper
│   └── midi.py           # routing + Basic Pitch (updated to accept MidiParams)
└── ui/
    ├── midi_params_widget.py   # expandable per-stem parameter panel
    └── output_panel.py         # integrate MidiParamsWidget per stem row
```

---

## Engine Routing

`core/midi.py` exposes a single public function:

```python
def convert_stem_to_midi(stem: str, wav_path: Path, output_dir: Path, params: MidiParams) -> Path
```

Routing is determined by stem name:

| Stem | Engine |
|---|---|
| `drums` | `drum_midi.convert_drums_to_midi()` |
| `piano` | `piano_midi.convert_piano_to_midi()` |
| `vocals`, `bass`, `guitar`, `other` | Basic Pitch with `params` |

---

## Parameters & Presets

`core/midi_params.py` defines the dataclass and frozen per-stem defaults:

```python
@dataclass
class MidiParams:
    onset_threshold: float = 0.50      # Basic Pitch / drum sensitivity
    frame_threshold: float = 0.30      # Basic Pitch only
    minimum_note_length: int = 58      # ms, Basic Pitch only
    minimum_frequency: float = 40.0   # Hz, Basic Pitch only
    maximum_frequency: float = 8000.0 # Hz, Basic Pitch only
    melodia_trick: bool = False        # Basic Pitch only
    sensitivity: float = 0.50         # drums only
```

Per-stem defaults (stored as `DEFAULTS: dict[str, MidiParams]`):

| Param | vocals | bass | guitar | other | drums |
|---|---|---|---|---|---|
| onset_threshold | 0.50 | 0.40 | 0.50 | 0.50 | — |
| frame_threshold | 0.30 | 0.25 | 0.30 | 0.30 | — |
| minimum_note_length (ms) | 80 | 100 | 58 | 58 | — |
| minimum_frequency (Hz) | 80 | 40 | 80 | 40 | — |
| maximum_frequency (Hz) | 1200 | 300 | 1200 | 8000 | — |
| melodia_trick | True | False | True | False | — |
| sensitivity | — | — | — | — | 0.50 |

Piano uses `piano_transcription_inference`'s internal defaults — no user-exposed params.

---

## Drum Engine

`core/drum_midi.py` uses `librosa` for onset detection and `pretty_midi` for MIDI output.

**Pipeline:**
1. Load WAV with `librosa.load()`
2. Detect onsets with `librosa.onset.onset_detect(backtrack=True)`; sensitivity param maps to `delta` argument
3. For each onset, compute spectral centroid of a 50 ms window
4. Classify into GM drum note by centroid range:
   - < 200 Hz → Kick (36)
   - 200–800 Hz → Snare (38)
   - 800–3000 Hz → Closed Hi-Hat (42)
   - ≥ 3000 Hz → Open Hi-Hat (46)
5. Write GM MIDI file via `pretty_midi` at channel 9, velocity 100

---

## Piano Engine

`core/piano_midi.py` wraps `piano_transcription_inference`:

```python
from piano_transcription_inference import PianoTranscription, load_audio, sample_rate

def convert_piano_to_midi(wav_path: Path, output_dir: Path) -> Path:
    transcriptor = PianoTranscription(device='cpu', checkpoint_path=None)
    audio, _ = load_audio(str(wav_path), sr=sample_rate, mono=True)
    dest = output_dir / "piano.mid"
    transcriptor.inference(audio, str(dest))
    return dest
```

Model weights (~100 MB) are downloaded on first use to `~/.cache/piano_transcription/`. No user-exposed parameters.

---

## UI Changes

### Output Panel

Each stem row in the "Convert to MIDI" group gains a gear button:

```
[✓] vocals    [⚙]
[✓] drums     [⚙]
[✓] bass      [⚙]
[✓] guitar    [⚙]
[✓] piano     [⚙]
[✓] other     [⚙]
```

Clicking ⚙ expands an inline `MidiParamsWidget` below that stem row. Only one panel is open at a time; clicking a second ⚙ closes the first.

### MidiParamsWidget

**Basic Pitch stems (vocals, bass, guitar, other):**
- Onset threshold — QSlider 0.10–0.90, step 0.05
- Frame threshold — QSlider 0.10–0.90, step 0.05
- Min note length — QSlider 10–500 ms, step 10
- Min frequency — QDoubleSpinBox 20–2000 Hz
- Max frequency — QDoubleSpinBox 200–20000 Hz (must be > min; shows red border if invalid)
- Melodia trick — QCheckBox
- "Reset to preset" link button — restores DEFAULTS[stem]

**Drums:**
- Sensitivity — QSlider 0.10–0.90, step 0.05
- "Reset to preset" link button

**Piano:**
- Label: "Using piano transcription model — no parameters needed."

Convert Selected and Open Folder buttons remain at the bottom, unchanged.

---

## Error Handling

| Failure | Behaviour |
|---|---|
| Piano model weights not cached | Progress bar shows "Downloading piano model…" before conversion starts; auto-downloads ~100 MB |
| No drum onsets detected | Per-stem error: "No drum hits detected — try lowering sensitivity" |
| Basic Pitch produces no MIDI file | Existing per-stem error behaviour unchanged |
| `piano_transcription_inference` fails | Per-stem error message; other stems continue converting |
| Frequency range min ≥ max | Min/max fields show red border; Convert Selected disabled for that stem until fixed |

---

## Technology Stack

| Component | Library | Notes |
|---|---|---|
| Drum onset detection | librosa | Transitive dep — add explicitly to requirements.txt |
| Drum MIDI output | pretty_midi | New dependency |
| Piano transcription | piano_transcription_inference | New dependency; ~100 MB model download on first use |
| Pitched stem conversion | basic-pitch | Existing; now accepts MidiParams |
