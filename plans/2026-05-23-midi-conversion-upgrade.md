# MIDI Conversion Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single fixed Basic Pitch MIDI conversion with a three-engine system (drums → onset detection, piano → dedicated model, all others → Basic Pitch with per-stem tunable presets) and add a gear-button UI to expose per-stem parameters.

**Architecture:** A new `core/midi_params.py` holds a `MidiParams` dataclass and frozen per-stem defaults. `core/midi.py` gains a routing function `convert_stem_to_midi` that dispatches to `drum_midi.py`, `piano_midi.py`, or Basic Pitch based on stem name. `ui/midi_params_widget.py` is a collapsible per-stem parameter panel embedded in an updated `ui/output_panel.py`.

**Tech Stack:** Python 3.11, PyQt6 6.6+, Basic Pitch (existing), librosa (onset detection), pretty_midi (drum MIDI writing), piano_transcription_inference (piano model), pytest

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `stem_splitter/core/midi_params.py` | MidiParams dataclass + DEFAULTS dict |
| Create | `stem_splitter/core/drum_midi.py` | librosa onset detection → GM MIDI via pretty_midi |
| Create | `stem_splitter/core/piano_midi.py` | piano_transcription_inference wrapper |
| Modify | `stem_splitter/core/midi.py` | Add convert_stem_to_midi routing; keep _convert_with_basic_pitch private |
| Modify | `stem_splitter/core/worker.py` | MidiWorker accepts list[dict] with stem/wav_path/params |
| Create | `stem_splitter/ui/midi_params_widget.py` | Expandable per-stem parameter panel |
| Modify | `stem_splitter/ui/output_panel.py` | Gear buttons per stem row, integrate MidiParamsWidget |
| Modify | `stem_splitter/ui/main_window.py` | Pass new list[dict] format from signal to MidiWorker |
| Modify | `requirements.txt` | Add librosa, pretty_midi, piano_transcription_inference |
| Create | `tests/test_midi_params.py` | Tests for MidiParams defaults |
| Create | `tests/test_drum_midi.py` | Tests for drum MIDI engine |
| Create | `tests/test_piano_midi.py` | Tests for piano MIDI wrapper |
| Modify | `tests/test_midi.py` | Update for new convert_stem_to_midi routing API |
| Modify | `tests/test_worker.py` | Update MidiWorker tests for new list[dict] format |

---

## Task 1: Install Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Install the three new packages**

```bash
.venv/bin/pip install librosa pretty_midi piano_transcription_inference
```

Expected output ends with: `Successfully installed ...`

- [ ] **Step 2: Verify imports work**

```bash
.venv/bin/python -c "import librosa; import pretty_midi; from piano_transcription_inference import PianoTranscription; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Add packages to requirements.txt**

Replace the contents of `requirements.txt` with:

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

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add librosa, pretty_midi, piano_transcription_inference dependencies"
```

---

## Task 2: MidiParams Dataclass

**Files:**
- Create: `stem_splitter/core/midi_params.py`
- Create: `tests/test_midi_params.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_midi_params.py`:

```python
from stem_splitter.core.midi_params import MidiParams, DEFAULTS


def test_midi_params_class_defaults():
    p = MidiParams()
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 58
    assert p.minimum_frequency == 40.0
    assert p.maximum_frequency == 8000.0
    assert p.melodia_trick is False
    assert p.sensitivity == 0.50


def test_defaults_vocals():
    p = DEFAULTS["vocals"]
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 80
    assert p.minimum_frequency == 80.0
    assert p.maximum_frequency == 1200.0
    assert p.melodia_trick is True


def test_defaults_bass():
    p = DEFAULTS["bass"]
    assert p.onset_threshold == 0.40
    assert p.frame_threshold == 0.25
    assert p.minimum_note_length == 100
    assert p.minimum_frequency == 40.0
    assert p.maximum_frequency == 300.0
    assert p.melodia_trick is False


def test_defaults_guitar():
    p = DEFAULTS["guitar"]
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 58
    assert p.minimum_frequency == 80.0
    assert p.maximum_frequency == 1200.0
    assert p.melodia_trick is True


def test_defaults_other():
    p = DEFAULTS["other"]
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 58
    assert p.minimum_frequency == 40.0
    assert p.maximum_frequency == 8000.0
    assert p.melodia_trick is False


def test_defaults_drums():
    p = DEFAULTS["drums"]
    assert p.sensitivity == 0.50


def test_defaults_piano():
    assert "piano" in DEFAULTS


def test_defaults_covers_all_stems():
    for stem in ["vocals", "bass", "guitar", "other", "drums", "piano"]:
        assert stem in DEFAULTS
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_midi_params.py -v
```

Expected: `ModuleNotFoundError: No module named 'stem_splitter.core.midi_params'`

- [ ] **Step 3: Implement MidiParams**

Create `stem_splitter/core/midi_params.py`:

```python
from dataclasses import dataclass


@dataclass
class MidiParams:
    onset_threshold: float = 0.50
    frame_threshold: float = 0.30
    minimum_note_length: int = 58
    minimum_frequency: float = 40.0
    maximum_frequency: float = 8000.0
    melodia_trick: bool = False
    sensitivity: float = 0.50


DEFAULTS: dict[str, MidiParams] = {
    "vocals": MidiParams(
        onset_threshold=0.50,
        frame_threshold=0.30,
        minimum_note_length=80,
        minimum_frequency=80.0,
        maximum_frequency=1200.0,
        melodia_trick=True,
    ),
    "bass": MidiParams(
        onset_threshold=0.40,
        frame_threshold=0.25,
        minimum_note_length=100,
        minimum_frequency=40.0,
        maximum_frequency=300.0,
        melodia_trick=False,
    ),
    "guitar": MidiParams(
        onset_threshold=0.50,
        frame_threshold=0.30,
        minimum_note_length=58,
        minimum_frequency=80.0,
        maximum_frequency=1200.0,
        melodia_trick=True,
    ),
    "other": MidiParams(
        onset_threshold=0.50,
        frame_threshold=0.30,
        minimum_note_length=58,
        minimum_frequency=40.0,
        maximum_frequency=8000.0,
        melodia_trick=False,
    ),
    "drums": MidiParams(sensitivity=0.50),
    "piano": MidiParams(),
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_midi_params.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/midi_params.py tests/test_midi_params.py
git commit -m "feat: add MidiParams dataclass and per-stem defaults"
```

---

## Task 3: Drum MIDI Engine

**Files:**
- Create: `stem_splitter/core/drum_midi.py`
- Create: `tests/test_drum_midi.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_drum_midi.py`:

```python
import numpy as np
import soundfile as sf
import pytest
from pathlib import Path
from stem_splitter.core.drum_midi import convert_drums_to_midi


@pytest.fixture
def drum_wav(tmp_path):
    sr = 22050
    audio = np.zeros(sr * 4, dtype=np.float32)
    # Four transient impulses at 0.5 s intervals — enough for onset_detect to find
    for t in [0.5, 1.0, 1.5, 2.0]:
        idx = int(t * sr)
        audio[idx : idx + 512] = np.random.default_rng(42).standard_normal(512).astype(np.float32)
    path = tmp_path / "drums.wav"
    sf.write(str(path), audio, sr)
    return path


def test_convert_drums_to_midi_returns_correct_path(drum_wav, tmp_path):
    result = convert_drums_to_midi(drum_wav, tmp_path, sensitivity=0.5)
    assert result == tmp_path / "drums.mid"


def test_convert_drums_to_midi_creates_file(drum_wav, tmp_path):
    result = convert_drums_to_midi(drum_wav, tmp_path, sensitivity=0.5)
    assert result.exists()


def test_convert_drums_to_midi_silent_wav_raises(tmp_path):
    sr = 22050
    audio = np.zeros(sr * 2, dtype=np.float32)
    wav_path = tmp_path / "silence.wav"
    sf.write(str(wav_path), audio, sr)
    with pytest.raises(RuntimeError, match="No drum hits detected"):
        convert_drums_to_midi(wav_path, tmp_path, sensitivity=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_drum_midi.py -v
```

Expected: `ModuleNotFoundError: No module named 'stem_splitter.core.drum_midi'`

- [ ] **Step 3: Implement drum MIDI engine**

Create `stem_splitter/core/drum_midi.py`:

```python
import numpy as np
import librosa
import pretty_midi
from pathlib import Path

_KICK = 36
_SNARE = 38
_CLOSED_HH = 42
_OPEN_HH = 46
_WINDOW_SEC = 0.05  # 50 ms spectral analysis window


def convert_drums_to_midi(wav_path: Path, output_dir: Path, sensitivity: float = 0.50) -> Path:
    audio, sr = librosa.load(str(wav_path), sr=None, mono=True)

    onset_frames = librosa.onset.onset_detect(
        y=audio, sr=sr, backtrack=True, delta=sensitivity * 0.1
    )
    if len(onset_frames) == 0:
        raise RuntimeError("No drum hits detected — try lowering sensitivity")

    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    window_samples = int(_WINDOW_SEC * sr)

    midi = pretty_midi.PrettyMIDI()
    drum_track = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for t in onset_times:
        start = int(t * sr)
        end = min(start + window_samples, len(audio))
        window = audio[start:end]

        if len(window) < 2:
            centroid = 1000.0
        else:
            S = np.abs(np.fft.rfft(window))
            freqs = np.fft.rfftfreq(len(window), d=1.0 / sr)
            centroid = float(np.sum(freqs * S) / (np.sum(S) + 1e-9))

        if centroid < 200:
            pitch = _KICK
        elif centroid < 800:
            pitch = _SNARE
        elif centroid < 3000:
            pitch = _CLOSED_HH
        else:
            pitch = _OPEN_HH

        note = pretty_midi.Note(
            velocity=100, pitch=pitch, start=float(t), end=float(t) + 0.1
        )
        drum_track.notes.append(note)

    midi.instruments.append(drum_track)
    dest = output_dir / "drums.mid"
    midi.write(str(dest))
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_drum_midi.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/drum_midi.py tests/test_drum_midi.py
git commit -m "feat: add drum MIDI engine using librosa onset detection"
```

---

## Task 4: Piano MIDI Engine

**Files:**
- Create: `stem_splitter/core/piano_midi.py`
- Create: `tests/test_piano_midi.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_piano_midi.py`:

```python
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from stem_splitter.core.piano_midi import convert_piano_to_midi


def test_convert_piano_to_midi_returns_correct_path(tmp_path):
    wav_path = tmp_path / "piano.wav"
    wav_path.write_bytes(b"fake")
    mock_audio = np.zeros(1000, dtype=np.float32)

    with patch("stem_splitter.core.piano_midi.PianoTranscription") as MockT, \
         patch("stem_splitter.core.piano_midi.load_audio", return_value=(mock_audio, 16000)):
        mock_t = MagicMock()
        MockT.return_value = mock_t
        result = convert_piano_to_midi(wav_path, tmp_path)

    assert result == tmp_path / "piano.mid"


def test_convert_piano_to_midi_calls_inference_with_correct_dest(tmp_path):
    wav_path = tmp_path / "piano.wav"
    wav_path.write_bytes(b"fake")
    mock_audio = np.zeros(1000, dtype=np.float32)

    with patch("stem_splitter.core.piano_midi.PianoTranscription") as MockT, \
         patch("stem_splitter.core.piano_midi.load_audio", return_value=(mock_audio, 16000)):
        mock_t = MagicMock()
        MockT.return_value = mock_t
        convert_piano_to_midi(wav_path, tmp_path)

    expected_dest = str(tmp_path / "piano.mid")
    mock_t.inference.assert_called_once_with(mock_audio, expected_dest)


def test_convert_piano_to_midi_uses_cpu_device(tmp_path):
    wav_path = tmp_path / "piano.wav"
    wav_path.write_bytes(b"fake")
    mock_audio = np.zeros(1000, dtype=np.float32)

    with patch("stem_splitter.core.piano_midi.PianoTranscription") as MockT, \
         patch("stem_splitter.core.piano_midi.load_audio", return_value=(mock_audio, 16000)):
        MockT.return_value = MagicMock()
        convert_piano_to_midi(wav_path, tmp_path)

    MockT.assert_called_once_with(device="cpu", checkpoint_path=None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_piano_midi.py -v
```

Expected: `ModuleNotFoundError: No module named 'stem_splitter.core.piano_midi'`

- [ ] **Step 3: Implement piano MIDI engine**

Create `stem_splitter/core/piano_midi.py`:

```python
from pathlib import Path
from piano_transcription_inference import PianoTranscription, load_audio, sample_rate


def convert_piano_to_midi(wav_path: Path, output_dir: Path) -> Path:
    transcriptor = PianoTranscription(device="cpu", checkpoint_path=None)
    audio, _ = load_audio(str(wav_path), sr=sample_rate, mono=True)
    dest = output_dir / "piano.mid"
    transcriptor.inference(audio, str(dest))
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_piano_midi.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/piano_midi.py tests/test_piano_midi.py
git commit -m "feat: add piano MIDI engine using piano_transcription_inference"
```

---

## Task 5: Routing Function in midi.py

**Files:**
- Modify: `stem_splitter/core/midi.py`
- Modify: `tests/test_midi.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_midi.py` entirely with:

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from stem_splitter.core.midi import convert_stem_to_midi
from stem_splitter.core.midi_params import MidiParams, DEFAULTS


def test_routing_drums_calls_drum_engine(tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    with patch("stem_splitter.core.midi.convert_drums_to_midi", return_value=tmp_path / "drums.mid") as mock_drum:
        convert_stem_to_midi("drums", wav, tmp_path, DEFAULTS["drums"])
    mock_drum.assert_called_once_with(wav, tmp_path, DEFAULTS["drums"].sensitivity)


def test_routing_piano_calls_piano_engine(tmp_path):
    wav = tmp_path / "piano.wav"
    wav.touch()
    with patch("stem_splitter.core.midi.convert_piano_to_midi", return_value=tmp_path / "piano.mid") as mock_piano:
        convert_stem_to_midi("piano", wav, tmp_path, DEFAULTS["piano"])
    mock_piano.assert_called_once_with(wav, tmp_path)


def test_routing_vocals_calls_basic_pitch(tmp_path):
    wav = tmp_path / "vocals.wav"
    wav.touch()

    def fake_predict(audio_paths, output_dir, **kwargs):
        Path(output_dir, "vocals_basic_pitch.mid").touch()

    with patch("stem_splitter.core.midi.predict_and_save", side_effect=fake_predict):
        result = convert_stem_to_midi("vocals", wav, tmp_path, DEFAULTS["vocals"])

    assert result == tmp_path / "vocals.mid"
    assert result.exists()


def test_routing_basic_pitch_passes_params(tmp_path):
    wav = tmp_path / "bass.wav"
    wav.touch()
    params = DEFAULTS["bass"]

    def fake_predict(audio_paths, output_dir, **kwargs):
        Path(output_dir, "bass_basic_pitch.mid").touch()

    with patch("stem_splitter.core.midi.predict_and_save", side_effect=fake_predict) as mock_bp:
        convert_stem_to_midi("bass", wav, tmp_path, params)

    call_kwargs = mock_bp.call_args.kwargs
    assert call_kwargs["onset_threshold"] == params.onset_threshold
    assert call_kwargs["frame_threshold"] == params.frame_threshold
    assert call_kwargs["minimum_note_length"] == params.minimum_note_length
    assert call_kwargs["minimum_frequency"] == params.minimum_frequency
    assert call_kwargs["maximum_frequency"] == params.maximum_frequency
    assert call_kwargs["melodia_trick"] == params.melodia_trick


def test_routing_basic_pitch_raises_if_no_output(tmp_path):
    wav = tmp_path / "guitar.wav"
    wav.touch()
    with patch("stem_splitter.core.midi.predict_and_save"):
        with pytest.raises(RuntimeError, match="did not produce a MIDI"):
            convert_stem_to_midi("guitar", wav, tmp_path, DEFAULTS["guitar"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_midi.py -v
```

Expected: `ImportError: cannot import name 'convert_stem_to_midi'`

- [ ] **Step 3: Rewrite midi.py**

Replace `stem_splitter/core/midi.py` entirely with:

```python
from pathlib import Path
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
from stem_splitter.core.midi_params import MidiParams
from stem_splitter.core.drum_midi import convert_drums_to_midi
from stem_splitter.core.piano_midi import convert_piano_to_midi


def convert_stem_to_midi(stem: str, wav_path: Path, output_dir: Path, params: MidiParams) -> Path:
    if stem == "drums":
        return convert_drums_to_midi(wav_path, output_dir, params.sensitivity)
    if stem == "piano":
        return convert_piano_to_midi(wav_path, output_dir)
    return _convert_with_basic_pitch(wav_path, output_dir, params)


def _convert_with_basic_pitch(wav_path: Path, output_dir: Path, params: MidiParams) -> Path:
    predict_and_save(
        [str(wav_path)],
        str(output_dir),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=params.onset_threshold,
        frame_threshold=params.frame_threshold,
        minimum_note_length=params.minimum_note_length,
        minimum_frequency=params.minimum_frequency,
        maximum_frequency=params.maximum_frequency,
        melodia_trick=params.melodia_trick,
    )
    midi_files = list(output_dir.glob(f"{wav_path.stem}*.mid"))
    if not midi_files:
        raise RuntimeError(f"Basic Pitch did not produce a MIDI file for {wav_path.name}")
    dest = output_dir / f"{wav_path.stem}.mid"
    midi_files[0].rename(dest)
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_midi.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Run full test suite to check nothing broke**

```bash
.venv/bin/pytest --ignore=tests/test_worker.py -v
```

Expected: all pass (test_worker.py still imports old `convert_to_midi` — fixed in Task 6)

- [ ] **Step 6: Commit**

```bash
git add stem_splitter/core/midi.py tests/test_midi.py
git commit -m "feat: add convert_stem_to_midi routing to drum, piano, and Basic Pitch engines"
```

---

## Task 6: Update MidiWorker

**Files:**
- Modify: `stem_splitter/core/worker.py`
- Modify: `tests/test_worker.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_worker.py`, replace the two `MidiWorker` tests (lines 34–56) and update the import at line 39. The full file becomes:

```python
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import QCoreApplication

@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)

from stem_splitter.core.worker import PipelineWorker, MidiWorker
from stem_splitter.core.midi_params import DEFAULTS


def test_pipeline_worker_emits_finished_for_local_file(tmp_path, qapp):
    wav = tmp_path / "track.wav"
    wav.touch()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    finished = []
    with patch("stem_splitter.core.worker.make_output_dir", return_value=output_dir), \
         patch("stem_splitter.core.worker.separate"):
        worker = PipelineWorker(str(wav), "My Track", is_url=False)
        worker.finished.connect(lambda p: finished.append(p))
        worker.run()
    assert finished == [output_dir]


def test_pipeline_worker_emits_error_on_failure(tmp_path, qapp):
    errors = []
    with patch("stem_splitter.core.worker.make_output_dir", side_effect=RuntimeError("boom")):
        worker = PipelineWorker(str(tmp_path / "track.wav"), "My Track", is_url=False)
        worker.error.connect(lambda msg: errors.append(msg))
        worker.run()
    assert errors == ["boom"]


def test_midi_worker_converts_all_selected_stems(tmp_path, qapp):
    stems = [
        {"stem": "bass", "wav_path": tmp_path / "bass.wav", "params": DEFAULTS["bass"]},
        {"stem": "guitar", "wav_path": tmp_path / "guitar.wav", "params": DEFAULTS["guitar"]},
    ]
    for item in stems:
        item["wav_path"].touch()
    finished = []
    with patch("stem_splitter.core.worker.convert_stem_to_midi") as mock_midi:
        worker = MidiWorker(stems, tmp_path)
        worker.finished.connect(lambda: finished.append(True))
        worker.run()
    assert mock_midi.call_count == 2
    assert finished == [True]


def test_midi_worker_emits_error_per_failed_stem_and_continues(tmp_path, qapp):
    stems = [
        {"stem": "bass", "wav_path": tmp_path / "bass.wav", "params": DEFAULTS["bass"]},
        {"stem": "guitar", "wav_path": tmp_path / "guitar.wav", "params": DEFAULTS["guitar"]},
    ]
    errors = []
    finished = []
    with patch("stem_splitter.core.worker.convert_stem_to_midi", side_effect=RuntimeError("fail")):
        worker = MidiWorker(stems, tmp_path)
        worker.error.connect(lambda stem, msg: errors.append((stem, msg)))
        worker.finished.connect(lambda: finished.append(True))
        worker.run()
    assert len(errors) == 2
    assert finished == [True]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_worker.py -v
```

Expected: failures on the two MidiWorker tests — `AttributeError` or `TypeError` because MidiWorker still takes `list[Path]`.

- [ ] **Step 3: Update worker.py**

Replace `stem_splitter/core/worker.py` entirely with:

```python
import tempfile
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from stem_splitter.core.downloader import download_audio
from stem_splitter.core.separator import separate
from stem_splitter.core.output import make_output_dir
from stem_splitter.core.midi import convert_stem_to_midi


class PipelineWorker(QThread):
    progress = pyqtSignal(str, int)   # stage, percent
    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(self, source: str, track_name: str, is_url: bool = False):
        super().__init__()
        self.source = source
        self.track_name = track_name
        self.is_url = is_url

    def run(self):
        try:
            if self.is_url:
                with tempfile.TemporaryDirectory() as tmp:
                    self.progress.emit("Downloading", 0)
                    audio_path = download_audio(self.source, Path(tmp))
                    self.progress.emit("Downloading", 100)
                    output_dir = make_output_dir(self.track_name)
                    self.progress.emit("Separating", 0)
                    separate(audio_path, output_dir)
                    self.progress.emit("Separating", 100)
                    self.finished.emit(output_dir)
            else:
                audio_path = Path(self.source)
                output_dir = make_output_dir(self.track_name)
                self.progress.emit("Separating", 0)
                separate(audio_path, output_dir)
                self.progress.emit("Separating", 100)
                self.finished.emit(output_dir)
        except Exception as e:
            self.error.emit(str(e))


class MidiWorker(QThread):
    progress = pyqtSignal(str, int)   # stem_name, percent
    finished = pyqtSignal()
    error = pyqtSignal(str, str)      # stem_name, message

    def __init__(self, stems: list, output_dir: Path):
        # stems: list of {"stem": str, "wav_path": Path, "params": MidiParams}
        super().__init__()
        self.stems = stems
        self.output_dir = output_dir

    def run(self):
        total = len(self.stems)
        for i, item in enumerate(self.stems):
            stem = item["stem"]
            wav_path = item["wav_path"]
            params = item["params"]
            try:
                self.progress.emit(stem, int(i / total * 100))
                convert_stem_to_midi(stem, wav_path, self.output_dir, params)
            except Exception as e:
                self.error.emit(stem, str(e))
        self.finished.emit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_worker.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Run the full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests pass (28+ tests)

- [ ] **Step 6: Commit**

```bash
git add stem_splitter/core/worker.py tests/test_worker.py
git commit -m "feat: update MidiWorker to use convert_stem_to_midi with per-stem params"
```

---

## Task 7: MidiParamsWidget

**Files:**
- Create: `stem_splitter/ui/midi_params_widget.py`

No dedicated test file — widget tests require a running QApplication and are covered by visual inspection. The widget is exercised via OutputPanel in the running app.

- [ ] **Step 1: Create MidiParamsWidget**

Create `stem_splitter/ui/midi_params_widget.py`:

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QCheckBox, QDoubleSpinBox, QPushButton,
)
from PyQt6.QtCore import Qt
from stem_splitter.core.midi_params import MidiParams, DEFAULTS


class MidiParamsWidget(QWidget):
    def __init__(self, stem: str, parent=None):
        super().__init__(parent)
        self._stem = stem
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 4, 4, 8)

        if stem == "piano":
            layout.addWidget(QLabel("Using piano transcription model — no parameters needed."))
            self._reset_btn = None
            return

        if stem == "drums":
            self._sensitivity = self._add_slider(layout, "Sensitivity", 10, 90, int(DEFAULTS["drums"].sensitivity * 100))
        else:
            d = DEFAULTS[stem]
            self._onset = self._add_slider(layout, "Onset threshold", 10, 90, int(d.onset_threshold * 100))
            self._frame = self._add_slider(layout, "Frame threshold", 10, 90, int(d.frame_threshold * 100))
            self._min_length = self._add_slider(layout, "Min note length (ms)", 10, 500, d.minimum_note_length)

            freq_row = QHBoxLayout()
            freq_row.addWidget(QLabel("Min freq (Hz)"))
            self._min_freq = QDoubleSpinBox()
            self._min_freq.setRange(20.0, 2000.0)
            self._min_freq.setValue(d.minimum_frequency)
            freq_row.addWidget(self._min_freq)
            freq_row.addWidget(QLabel("Max freq (Hz)"))
            self._max_freq = QDoubleSpinBox()
            self._max_freq.setRange(200.0, 20000.0)
            self._max_freq.setValue(d.maximum_frequency)
            freq_row.addWidget(self._max_freq)
            layout.addLayout(freq_row)

            self._min_freq.valueChanged.connect(self._validate_freq)
            self._max_freq.valueChanged.connect(self._validate_freq)

            self._melodia = QCheckBox("Melodia trick")
            self._melodia.setChecked(d.melodia_trick)
            layout.addWidget(self._melodia)

        self._reset_btn = QPushButton("Reset to preset")
        self._reset_btn.clicked.connect(self._reset)
        layout.addWidget(self._reset_btn)

    def _add_slider(self, layout: QVBoxLayout, label: str, min_val: int, max_val: int, value: int) -> QSlider:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(value)
        val_label = QLabel(str(value))
        val_label.setFixedWidth(36)
        slider.valueChanged.connect(val_label.setNum)
        row.addWidget(slider)
        row.addWidget(val_label)
        layout.addLayout(row)
        return slider

    def _validate_freq(self):
        invalid = self._min_freq.value() >= self._max_freq.value()
        style = "border: 1px solid red;" if invalid else ""
        self._min_freq.setStyleSheet(style)
        self._max_freq.setStyleSheet(style)

    def get_params(self) -> MidiParams:
        if self._stem == "piano":
            return DEFAULTS["piano"]
        if self._stem == "drums":
            return MidiParams(sensitivity=self._sensitivity.value() / 100.0)
        return MidiParams(
            onset_threshold=self._onset.value() / 100.0,
            frame_threshold=self._frame.value() / 100.0,
            minimum_note_length=self._min_length.value(),
            minimum_frequency=self._min_freq.value(),
            maximum_frequency=self._max_freq.value(),
            melodia_trick=self._melodia.isChecked(),
        )

    def _reset(self):
        d = DEFAULTS[self._stem]
        if self._stem == "drums":
            self._sensitivity.setValue(int(d.sensitivity * 100))
        elif self._stem != "piano":
            self._onset.setValue(int(d.onset_threshold * 100))
            self._frame.setValue(int(d.frame_threshold * 100))
            self._min_length.setValue(d.minimum_note_length)
            self._min_freq.setValue(d.minimum_frequency)
            self._max_freq.setValue(d.maximum_frequency)
            self._melodia.setChecked(d.melodia_trick)
```

- [ ] **Step 2: Verify import works**

```bash
.venv/bin/python -c "from stem_splitter.ui.midi_params_widget import MidiParamsWidget; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add stem_splitter/ui/midi_params_widget.py
git commit -m "feat: add MidiParamsWidget with per-stem parameter controls"
```

---

## Task 8: Update OutputPanel

**Files:**
- Modify: `stem_splitter/ui/output_panel.py`

- [ ] **Step 1: Replace output_panel.py**

Replace `stem_splitter/ui/output_panel.py` entirely with:

```python
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QGroupBox,
)
from PyQt6.QtCore import pyqtSignal
from stem_splitter.core.output import STEMS
from stem_splitter.ui.midi_params_widget import MidiParamsWidget


class OutputPanel(QWidget):
    # Emits list of dicts: [{"stem": str, "wav_path": Path, "params": MidiParams}, ...]
    convert_midi_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output_dir: Path | None = None
        self._checkboxes: dict[str, QCheckBox] = {}
        self._params_widgets: dict[str, MidiParamsWidget] = {}
        self._gear_btns: dict[str, QPushButton] = {}
        self._active_stem: str | None = None

        layout = QVBoxLayout(self)
        self._path_label = QLabel("")
        layout.addWidget(self._path_label)

        midi_box = QGroupBox("Convert to MIDI")
        midi_layout = QVBoxLayout(midi_box)

        for stem in STEMS:
            row = QHBoxLayout()

            cb = QCheckBox(stem)
            cb.setChecked(stem != "drums")
            self._checkboxes[stem] = cb
            row.addWidget(cb)
            row.addStretch()

            gear_btn = QPushButton("⚙")
            gear_btn.setFixedWidth(30)
            gear_btn.setCheckable(True)
            gear_btn.clicked.connect(lambda _checked, s=stem: self._on_gear(s))
            self._gear_btns[stem] = gear_btn
            row.addWidget(gear_btn)

            midi_layout.addLayout(row)

            params_widget = MidiParamsWidget(stem)
            params_widget.setVisible(False)
            self._params_widgets[stem] = params_widget
            midi_layout.addWidget(params_widget)

        layout.addWidget(midi_box)

        buttons = QHBoxLayout()
        self._convert_btn = QPushButton("Convert Selected")
        self._convert_btn.clicked.connect(self._on_convert)
        self._open_btn = QPushButton("Open Folder")
        self._open_btn.clicked.connect(self._on_open_folder)
        buttons.addWidget(self._convert_btn)
        buttons.addWidget(self._open_btn)
        layout.addLayout(buttons)

        self.setVisible(False)

    def _on_gear(self, stem: str):
        if self._active_stem == stem:
            self._params_widgets[stem].setVisible(False)
            self._gear_btns[stem].setChecked(False)
            self._active_stem = None
        else:
            if self._active_stem is not None:
                self._params_widgets[self._active_stem].setVisible(False)
                self._gear_btns[self._active_stem].setChecked(False)
            self._params_widgets[stem].setVisible(True)
            self._active_stem = stem

    def show_results(self, output_dir: Path):
        self._output_dir = output_dir
        self._path_label.setText(str(output_dir))
        self.setVisible(True)

    def _on_convert(self):
        if not self._output_dir:
            return
        selected = [
            {
                "stem": stem,
                "wav_path": self._output_dir / f"{stem}.wav",
                "params": self._params_widgets[stem].get_params(),
            }
            for stem, cb in self._checkboxes.items()
            if cb.isChecked()
        ]
        self.convert_midi_requested.emit(selected)

    def _on_open_folder(self):
        if self._output_dir:
            subprocess.run(["open", str(self._output_dir)])
```

- [ ] **Step 2: Verify import works**

```bash
.venv/bin/python -c "from stem_splitter.ui.output_panel import OutputPanel; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run the full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add stem_splitter/ui/output_panel.py
git commit -m "feat: add gear buttons and MidiParamsWidget to OutputPanel"
```

---

## Task 9: Update MainWindow

**Files:**
- Modify: `stem_splitter/ui/main_window.py`

The `_on_convert_midi` method currently converts a `list[Path]` into `MidiWorker(stem_paths, output_dir)`. It now receives `list[dict]` directly and needs no conversion.

- [ ] **Step 1: Update _on_convert_midi in main_window.py**

Replace `stem_splitter/ui/main_window.py` entirely with:

```python
from pathlib import Path
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QMessageBox
from stem_splitter.ui.source_panel import SourcePanel
from stem_splitter.ui.progress_panel import ProgressPanel
from stem_splitter.ui.output_panel import OutputPanel
from stem_splitter.core.worker import PipelineWorker, MidiWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stem Splitter")
        self.setMinimumWidth(600)
        self._worker: PipelineWorker | None = None
        self._midi_worker: MidiWorker | None = None

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

- [ ] **Step 2: Run the full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests pass

- [ ] **Step 3: Launch the app and verify the UI**

```bash
pkill -f "stem_splitter.main"; sleep 1
.venv/bin/python -m stem_splitter.main &
```

Check:
- Each stem row shows a checkbox and a ⚙ button
- Clicking ⚙ expands the parameter panel for that stem
- Clicking a second ⚙ closes the first panel and opens the second
- Piano panel shows "Using piano transcription model — no parameters needed."
- Drums panel shows only Sensitivity slider
- Other stems show onset threshold, frame threshold, min note length, min/max frequency, melodia trick checkbox
- "Reset to preset" restores slider values to defaults
- Setting min freq > max freq shows red borders on both fields

- [ ] **Step 4: Commit**

```bash
git add stem_splitter/ui/main_window.py
git commit -m "feat: wire OutputPanel convert_midi_requested to MidiWorker with per-stem params"
```
