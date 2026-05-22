# Stem Splitter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS desktop app that separates audio into 6 stems via Demucs and optionally converts stems to MIDI via Basic Pitch, accepting YouTube URLs, local files, or Apple Music system audio via BlackHole.

**Architecture:** PyQt6 single-window GUI with three source tabs. Core DSP logic in `stem_splitter/core/` never imports from `ui/`. A `QThread` worker runs the download+separation pipeline in the background, emitting signals for progress and completion. A separate `MidiWorker` handles optional per-stem MIDI conversion after separation.

**Tech Stack:** Python 3.11+, PyQt6 6.6+, yt-dlp, demucs (htdemucs_6s), basic-pitch, sounddevice, soundfile, numpy, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `stem_splitter/core/output.py` | `STEMS` constant, output directory creation, collision handling, path helpers |
| `stem_splitter/core/downloader.py` | yt-dlp wrapper — YouTube URL → WAV |
| `stem_splitter/core/recorder.py` | sounddevice/BlackHole wrapper — live capture → WAV |
| `stem_splitter/core/separator.py` | Demucs wrapper — audio file → 6 stem WAVs |
| `stem_splitter/core/midi.py` | Basic Pitch wrapper — stem WAV → MIDI |
| `stem_splitter/core/worker.py` | `PipelineWorker` and `MidiWorker` QThreads |
| `stem_splitter/ui/progress_panel.py` | Progress bar widgets (download, separate, MIDI) |
| `stem_splitter/ui/output_panel.py` | Stem list, MIDI checkboxes, Open Folder button |
| `stem_splitter/ui/source_panel.py` | Tabbed source input (YouTube / Local File / Apple Music) |
| `stem_splitter/ui/main_window.py` | Main PyQt6 window, wires all panels and workers |
| `stem_splitter/main.py` | Entry point |
| `tests/test_output.py` | Tests for output.py |
| `tests/test_downloader.py` | Tests for downloader.py |
| `tests/test_recorder.py` | Tests for recorder.py |
| `tests/test_separator.py` | Tests for separator.py |
| `tests/test_midi.py` | Tests for midi.py |
| `tests/test_worker.py` | Tests for worker.py |
| `requirements.txt` | Python dependencies |
| `pyproject.toml` | Project config and pytest settings |

---

## Task 1: Project setup

**Files:**
- Create: `stem_splitter/__init__.py`
- Create: `stem_splitter/core/__init__.py`
- Create: `stem_splitter/ui/__init__.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `pyproject.toml`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p stem_splitter/core stem_splitter/ui tests
touch stem_splitter/__init__.py stem_splitter/core/__init__.py stem_splitter/ui/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create `requirements.txt`**

```
PyQt6>=6.6.0
yt-dlp
demucs
basic-pitch
sounddevice
soundfile
numpy
pytest
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install without error. Demucs model weights are NOT downloaded at this step — they download on first use.

- [ ] **Step 5: Verify pytest collects nothing without error**

```bash
pytest --collect-only
```

Expected: `no tests ran`, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add stem_splitter/ tests/ requirements.txt pyproject.toml
git commit -m "chore: scaffold project structure and dependencies"
```

---

## Task 2: `core/output.py` — output directory management

**Files:**
- Create: `stem_splitter/core/output.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Write failing tests**

`tests/test_output.py`:
```python
from pathlib import Path
from stem_splitter.core.output import make_output_dir, stem_paths, midi_path, STEMS

def test_stems_list():
    assert STEMS == ["vocals", "drums", "bass", "guitar", "piano", "other"]

def test_make_output_dir_creates_directory(tmp_path):
    result = make_output_dir("My Song", base_dir=tmp_path)
    assert result == tmp_path / "My Song"
    assert result.is_dir()

def test_make_output_dir_handles_collision(tmp_path):
    (tmp_path / "My Song").mkdir()
    result = make_output_dir("My Song", base_dir=tmp_path)
    assert result == tmp_path / "My Song (2)"
    assert result.is_dir()

def test_make_output_dir_handles_multiple_collisions(tmp_path):
    (tmp_path / "My Song").mkdir()
    (tmp_path / "My Song (2)").mkdir()
    result = make_output_dir("My Song", base_dir=tmp_path)
    assert result == tmp_path / "My Song (3)"
    assert result.is_dir()

def test_stem_paths_returns_all_six(tmp_path):
    paths = stem_paths(tmp_path)
    assert set(paths.keys()) == set(STEMS)
    assert all(p.parent == tmp_path for p in paths.values())
    assert all(p.suffix == ".wav" for p in paths.values())

def test_midi_path(tmp_path):
    assert midi_path(tmp_path, "bass") == tmp_path / "bass.mid"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_output.py -v
```

Expected: `ImportError: No module named 'stem_splitter.core.output'`

- [ ] **Step 3: Implement `stem_splitter/core/output.py`**

```python
from pathlib import Path

MUSIC_TRACKS_DIR = Path.home() / "Documents" / "music_tracks"
STEMS = ["vocals", "drums", "bass", "guitar", "piano", "other"]

def make_output_dir(track_name: str, base_dir: Path = MUSIC_TRACKS_DIR) -> Path:
    candidate = base_dir / track_name
    if not candidate.exists():
        candidate.mkdir(parents=True)
        return candidate
    n = 2
    while True:
        candidate = base_dir / f"{track_name} ({n})"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
        n += 1

def stem_paths(output_dir: Path) -> dict[str, Path]:
    return {stem: output_dir / f"{stem}.wav" for stem in STEMS}

def midi_path(output_dir: Path, stem: str) -> Path:
    return output_dir / f"{stem}.mid"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_output.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/output.py tests/test_output.py
git commit -m "feat: add output directory management"
```

---

## Task 3: `core/downloader.py` — YouTube download

**Files:**
- Create: `stem_splitter/core/downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: Write failing tests**

`tests/test_downloader.py`:
```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from stem_splitter.core.downloader import is_valid_youtube_url, download_audio

def test_valid_youtube_watch_url():
    assert is_valid_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

def test_valid_youtu_be_url():
    assert is_valid_youtube_url("https://youtu.be/dQw4w9WgXcQ") is True

def test_invalid_url_returns_false():
    assert is_valid_youtube_url("https://soundcloud.com/track") is False

def test_empty_url_returns_false():
    assert is_valid_youtube_url("") is False

def test_download_audio_calls_yt_dlp(tmp_path):
    fake_wav = tmp_path / "My Track.wav"
    fake_wav.touch()
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = download_audio("https://www.youtube.com/watch?v=abc", tmp_path)
    args = mock_run.call_args[0][0]
    assert "yt-dlp" in args
    assert "-x" in args
    assert "--audio-format" in args
    assert "wav" in args
    assert result == fake_wav

def test_download_audio_raises_if_no_wav_produced(tmp_path):
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with pytest.raises(RuntimeError, match="did not produce a WAV"):
            download_audio("https://www.youtube.com/watch?v=abc", tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_downloader.py -v
```

Expected: `ImportError: No module named 'stem_splitter.core.downloader'`

- [ ] **Step 3: Implement `stem_splitter/core/downloader.py`**

```python
import subprocess
from pathlib import Path

def is_valid_youtube_url(url: str) -> bool:
    return "youtube.com/watch" in url or "youtu.be/" in url

def download_audio(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "wav",
         "-o", str(dest_dir / "%(title)s.%(ext)s"), url],
        capture_output=True, text=True, check=True,
    )
    wav_files = list(dest_dir.glob("*.wav"))
    if not wav_files:
        raise RuntimeError(f"yt-dlp did not produce a WAV file for {url!r}")
    return wav_files[0]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_downloader.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/downloader.py tests/test_downloader.py
git commit -m "feat: add YouTube audio downloader"
```

---

## Task 4: `core/recorder.py` — BlackHole system audio capture

**Files:**
- Create: `stem_splitter/core/recorder.py`
- Create: `tests/test_recorder.py`

- [ ] **Step 1: Write failing tests**

`tests/test_recorder.py`:
```python
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from stem_splitter.core.recorder import is_blackhole_available, Recorder

MOCK_DEVICES = [
    {"name": "Built-in Microphone", "max_input_channels": 2},
    {"name": "BlackHole 2ch", "max_input_channels": 2},
    {"name": "Built-in Output", "max_input_channels": 0},
]

def test_blackhole_detected_when_present():
    with patch("stem_splitter.core.recorder.sd.query_devices", return_value=MOCK_DEVICES):
        assert is_blackhole_available() is True

def test_blackhole_not_detected_when_absent():
    with patch("stem_splitter.core.recorder.sd.query_devices", return_value=[
        {"name": "Built-in Microphone", "max_input_channels": 2}
    ]):
        assert is_blackhole_available() is False

def test_recorder_start_raises_if_blackhole_missing():
    with patch("stem_splitter.core.recorder.sd.query_devices", return_value=[]):
        recorder = Recorder()
        with pytest.raises(RuntimeError, match="BlackHole 2ch not found"):
            recorder.start()

def test_recorder_stop_writes_wav(tmp_path):
    recorder = Recorder()
    recorder._frames = [np.zeros((1024, 2), dtype=np.float32)]
    recorder._stream = MagicMock()
    with patch("stem_splitter.core.recorder.sf.write") as mock_write:
        dest = tmp_path / "recording.wav"
        recorder.stop(dest)
    recorder._stream.stop.assert_called_once()
    recorder._stream.close.assert_called_once()
    assert mock_write.called
    assert str(dest) in mock_write.call_args[0][0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_recorder.py -v
```

Expected: `ImportError: No module named 'stem_splitter.core.recorder'`

- [ ] **Step 3: Implement `stem_splitter/core/recorder.py`**

```python
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path

BLACKHOLE_NAME = "BlackHole 2ch"
SAMPLE_RATE = 44100

def _blackhole_device_index() -> int | None:
    for i, dev in enumerate(sd.query_devices()):
        if BLACKHOLE_NAME in dev["name"] and dev["max_input_channels"] > 0:
            return i
    return None

def is_blackhole_available() -> bool:
    return _blackhole_device_index() is not None

class Recorder:
    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        device = _blackhole_device_index()
        if device is None:
            raise RuntimeError("BlackHole 2ch not found")
        self._frames = []
        self._stream = sd.InputStream(
            device=device, samplerate=SAMPLE_RATE, channels=2,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time, status):
        self._frames.append(indata.copy())

    def stop(self, dest_path: Path) -> Path:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        audio = np.concatenate(self._frames, axis=0)
        sf.write(str(dest_path), audio, SAMPLE_RATE)
        return dest_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_recorder.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/recorder.py tests/test_recorder.py
git commit -m "feat: add BlackHole system audio recorder"
```

---

## Task 5: `core/separator.py` — Demucs stem separation

**Files:**
- Create: `stem_splitter/core/separator.py`
- Create: `tests/test_separator.py`

- [ ] **Step 1: Write failing tests**

`tests/test_separator.py`:
```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from stem_splitter.core.separator import separate, MODEL
from stem_splitter.core.output import STEMS

def _make_demucs_output(tmp_path, track_stem):
    demucs_dir = tmp_path / MODEL / track_stem
    demucs_dir.mkdir(parents=True)
    for stem in STEMS:
        (demucs_dir / f"{stem}.wav").touch()

def test_separate_calls_demucs(tmp_path):
    audio = tmp_path / "track.wav"
    audio.touch()
    _make_demucs_output(tmp_path, "track")
    with patch("stem_splitter.core.separator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        separate(audio, tmp_path)
    args = mock_run.call_args[0][0]
    assert "demucs" in " ".join(args)
    assert MODEL in args

def test_separate_returns_stem_paths(tmp_path):
    audio = tmp_path / "track.wav"
    audio.touch()
    _make_demucs_output(tmp_path, "track")
    with patch("stem_splitter.core.separator.subprocess.run"):
        result = separate(audio, tmp_path)
    assert set(result.keys()) == set(STEMS)
    for stem, path in result.items():
        assert path == tmp_path / f"{stem}.wav"
        assert path.exists()

def test_separate_raises_on_demucs_failure(tmp_path):
    audio = tmp_path / "track.wav"
    audio.touch()
    with patch("stem_splitter.core.separator.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("demucs failed")
        with pytest.raises(Exception, match="demucs failed"):
            separate(audio, tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_separator.py -v
```

Expected: `ImportError: No module named 'stem_splitter.core.separator'`

- [ ] **Step 3: Implement `stem_splitter/core/separator.py`**

```python
import subprocess
from pathlib import Path
from stem_splitter.core.output import STEMS

MODEL = "htdemucs_6s"

def separate(audio_path: Path, output_dir: Path) -> dict[str, Path]:
    subprocess.run(
        ["python", "-m", "demucs", "-n", MODEL, "-o", str(output_dir), str(audio_path)],
        check=True,
    )
    track_name = audio_path.stem
    demucs_dir = output_dir / MODEL / track_name
    result = {}
    for stem in STEMS:
        src = demucs_dir / f"{stem}.wav"
        dest = output_dir / f"{stem}.wav"
        src.rename(dest)
        result[stem] = dest
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_separator.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/separator.py tests/test_separator.py
git commit -m "feat: add Demucs stem separator"
```

---

## Task 6: `core/midi.py` — Basic Pitch MIDI conversion

**Files:**
- Create: `stem_splitter/core/midi.py`
- Create: `tests/test_midi.py`

- [ ] **Step 1: Write failing tests**

`tests/test_midi.py`:
```python
import pytest
from pathlib import Path
from unittest.mock import patch
from stem_splitter.core.midi import convert_to_midi

def test_convert_to_midi_renames_output(tmp_path):
    wav = tmp_path / "bass.wav"
    wav.touch()

    def fake_predict(audio_paths, output_dir, **kwargs):
        Path(output_dir, "bass_basic_pitch.mid").touch()

    with patch("stem_splitter.core.midi.predict_and_save", side_effect=fake_predict):
        result = convert_to_midi(wav, tmp_path)

    assert result == tmp_path / "bass.mid"
    assert result.exists()

def test_convert_to_midi_raises_if_no_output(tmp_path):
    wav = tmp_path / "bass.wav"
    wav.touch()
    with patch("stem_splitter.core.midi.predict_and_save"):
        with pytest.raises(RuntimeError, match="did not produce a MIDI"):
            convert_to_midi(wav, tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_midi.py -v
```

Expected: `ImportError: No module named 'stem_splitter.core.midi'`

- [ ] **Step 3: Implement `stem_splitter/core/midi.py`**

```python
from pathlib import Path
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH

def convert_to_midi(wav_path: Path, output_dir: Path) -> Path:
    predict_and_save(
        [str(wav_path)],
        str(output_dir),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
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
pytest tests/test_midi.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/midi.py tests/test_midi.py
git commit -m "feat: add Basic Pitch MIDI converter"
```

---

## Task 7: `core/worker.py` — QThread pipeline and MIDI workers

**Files:**
- Create: `stem_splitter/core/worker.py`
- Create: `tests/test_worker.py`

- [ ] **Step 1: Write failing tests**

`tests/test_worker.py`:
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
    stems = [tmp_path / "bass.wav", tmp_path / "guitar.wav"]
    for s in stems:
        s.touch()
    finished = []
    with patch("stem_splitter.core.worker.convert_to_midi") as mock_midi:
        worker = MidiWorker(stems, tmp_path)
        worker.finished.connect(lambda: finished.append(True))
        worker.run()
    assert mock_midi.call_count == 2
    assert finished == [True]

def test_midi_worker_emits_error_per_failed_stem_and_continues(tmp_path, qapp):
    stems = [tmp_path / "bass.wav", tmp_path / "guitar.wav"]
    errors = []
    finished = []
    with patch("stem_splitter.core.worker.convert_to_midi", side_effect=RuntimeError("fail")):
        worker = MidiWorker(stems, tmp_path)
        worker.error.connect(lambda stem, msg: errors.append((stem, msg)))
        worker.finished.connect(lambda: finished.append(True))
        worker.run()
    assert len(errors) == 2
    assert finished == [True]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_worker.py -v
```

Expected: `ImportError: No module named 'stem_splitter.core.worker'`

- [ ] **Step 3: Implement `stem_splitter/core/worker.py`**

```python
import tempfile
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from stem_splitter.core.downloader import download_audio
from stem_splitter.core.separator import separate
from stem_splitter.core.output import make_output_dir
from stem_splitter.core.midi import convert_to_midi


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

    def __init__(self, stems: list[Path], output_dir: Path):
        super().__init__()
        self.stems = stems
        self.output_dir = output_dir

    def run(self):
        total = len(self.stems)
        for i, wav_path in enumerate(self.stems):
            try:
                self.progress.emit(wav_path.stem, int(i / total * 100))
                convert_to_midi(wav_path, self.output_dir)
            except Exception as e:
                self.error.emit(wav_path.stem, str(e))
        self.finished.emit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_worker.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/worker.py tests/test_worker.py
git commit -m "feat: add pipeline and MIDI QThread workers"
```

---

## Task 8: `ui/progress_panel.py` — progress bars

**Files:**
- Create: `stem_splitter/ui/progress_panel.py`

No unit tests — verify visually in Task 12.

- [ ] **Step 1: Implement `stem_splitter/ui/progress_panel.py`**

```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._download_label = QLabel("Downloading...")
        self._download_bar = QProgressBar()
        self._download_bar.setRange(0, 100)

        self._separate_label = QLabel("Separating...")
        self._separate_bar = QProgressBar()
        self._separate_bar.setRange(0, 100)

        self._midi_label = QLabel("Converting to MIDI...")
        self._midi_bar = QProgressBar()
        self._midi_bar.setRange(0, 100)

        for w in [self._download_label, self._download_bar,
                  self._separate_label, self._separate_bar,
                  self._midi_label, self._midi_bar]:
            layout.addWidget(w)

        self.reset()

    def reset(self):
        self.setVisible(False)

    def show_download(self):
        self.setVisible(True)
        self._download_label.setVisible(True)
        self._download_bar.setVisible(True)
        self._download_bar.setValue(0)
        self._separate_label.setVisible(False)
        self._separate_bar.setVisible(False)
        self._midi_label.setVisible(False)
        self._midi_bar.setVisible(False)

    def show_separate(self):
        self.setVisible(True)
        self._download_label.setVisible(False)
        self._download_bar.setVisible(False)
        self._separate_label.setVisible(True)
        self._separate_bar.setVisible(True)
        self._separate_bar.setValue(0)
        self._midi_label.setVisible(False)
        self._midi_bar.setVisible(False)

    def show_midi(self):
        self.setVisible(True)
        self._download_label.setVisible(False)
        self._download_bar.setVisible(False)
        self._separate_label.setVisible(False)
        self._separate_bar.setVisible(False)
        self._midi_label.setVisible(True)
        self._midi_bar.setVisible(True)
        self._midi_bar.setValue(0)

    def update_progress(self, stage: str, value: int):
        if stage == "Downloading":
            self._download_bar.setValue(value)
        elif stage == "Separating":
            self._separate_bar.setValue(value)
        else:
            self._midi_bar.setValue(value)
```

- [ ] **Step 2: Commit**

```bash
git add stem_splitter/ui/progress_panel.py
git commit -m "feat: add progress panel widget"
```

---

## Task 9: `ui/output_panel.py` — stem list and MIDI controls

**Files:**
- Create: `stem_splitter/ui/output_panel.py`

- [ ] **Step 1: Implement `stem_splitter/ui/output_panel.py`**

```python
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QGroupBox, QGridLayout,
)
from PyQt6.QtCore import pyqtSignal
from stem_splitter.core.output import STEMS


class OutputPanel(QWidget):
    convert_midi_requested = pyqtSignal(list)   # list[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output_dir: Path | None = None
        self._checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        self._path_label = QLabel("")
        layout.addWidget(self._path_label)

        midi_box = QGroupBox("Convert to MIDI")
        grid = QGridLayout(midi_box)
        for i, stem in enumerate(STEMS):
            cb = QCheckBox(stem)
            cb.setChecked(stem != "drums")
            if stem == "drums":
                cb.setToolTip(
                    "Drum-to-MIDI transcription is unreliable — results may be inaccurate."
                )
            self._checkboxes[stem] = cb
            grid.addWidget(cb, i // 3, i % 3)
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

    def show_results(self, output_dir: Path):
        self._output_dir = output_dir
        self._path_label.setText(str(output_dir))
        self.setVisible(True)

    def _on_convert(self):
        if not self._output_dir:
            return
        selected = [
            self._output_dir / f"{stem}.wav"
            for stem, cb in self._checkboxes.items()
            if cb.isChecked()
        ]
        self.convert_midi_requested.emit(selected)

    def _on_open_folder(self):
        if self._output_dir:
            subprocess.run(["open", str(self._output_dir)])
```

- [ ] **Step 2: Commit**

```bash
git add stem_splitter/ui/output_panel.py
git commit -m "feat: add output panel with MIDI stem selection"
```

---

## Task 10: `ui/source_panel.py` — tabbed source input

**Files:**
- Create: `stem_splitter/ui/source_panel.py`

- [ ] **Step 1: Implement `stem_splitter/ui/source_panel.py`**

```python
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLineEdit, QPushButton, QLabel, QFileDialog,
)
from PyQt6.QtCore import pyqtSignal
from stem_splitter.core.downloader import is_valid_youtube_url
from stem_splitter.core.recorder import is_blackhole_available, Recorder


class SourcePanel(QWidget):
    start_pipeline = pyqtSignal(str, str, bool)   # source, track_name, is_url

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recorder: Recorder | None = None

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._make_youtube_tab(), "YouTube URL")
        tabs.addTab(self._make_local_tab(), "Local File")
        tabs.addTab(self._make_apple_music_tab(), "Apple Music")
        layout.addWidget(tabs)

    # ── YouTube tab ──────────────────────────────────────────────────────────

    def _make_youtube_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("YouTube URL or paste link here")
        self._url_start_btn = QPushButton("Start")
        self._url_start_btn.clicked.connect(self._on_url_start)
        row.addWidget(self._url_input)
        row.addWidget(self._url_start_btn)
        self._url_error = QLabel("")
        self._url_error.setStyleSheet("color: red;")
        layout.addLayout(row)
        layout.addWidget(self._url_error)
        return w

    def _on_url_start(self):
        url = self._url_input.text().strip()
        if not is_valid_youtube_url(url):
            self._url_error.setText("Invalid YouTube URL")
            return
        self._url_error.setText("")
        track_name = url.split("v=")[-1] if "v=" in url else url.split("/")[-1]
        self.start_pipeline.emit(url, track_name, True)

    # ── Local File tab ────────────────────────────────────────────────────────

    def _make_local_tab(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("File path")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._on_browse)
        start = QPushButton("Start")
        start.clicked.connect(self._on_file_start)
        row.addWidget(self._file_input)
        row.addWidget(browse)
        row.addWidget(start)
        return w

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select audio file", "",
            "Audio Files (*.mp3 *.wav *.flac *.m4a)"
        )
        if path:
            self._file_input.setText(path)

    def _on_file_start(self):
        path = self._file_input.text().strip()
        if not path:
            return
        self.start_pipeline.emit(path, Path(path).stem, False)

    # ── Apple Music tab ───────────────────────────────────────────────────────

    def _make_apple_music_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        if not is_blackhole_available():
            layout.addWidget(QLabel(
                "⚠ BlackHole 2ch not detected.\n\n"
                "Install BlackHole and create a Multi-Output Device in\n"
                "macOS Audio MIDI Setup so audio routes to both your\n"
                "speakers and BlackHole simultaneously.\n\n"
                "Download: https://existential.audio/blackhole/"
            ))
            return w

        layout.addWidget(QLabel("1. Play the track in Apple Music\n2. Press Record when ready"))

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Track name:"))
        self._track_name_input = QLineEdit()
        name_row.addWidget(self._track_name_input)
        layout.addLayout(name_row)

        btn_row = QHBoxLayout()
        self._record_btn = QPushButton("● Record")
        self._record_btn.clicked.connect(self._on_record)
        self._stop_btn = QPushButton("■ Stop & Split")
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._record_btn)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)
        return w

    def _on_record(self):
        self._recorder = Recorder()
        self._recorder.start()
        self._record_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _on_stop(self):
        if not self._recorder:
            return
        tmp = tempfile.mktemp(suffix=".wav")
        self._recorder.stop(Path(tmp))
        self._record_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        track_name = self._track_name_input.text().strip() or "Apple Music Recording"
        self.start_pipeline.emit(tmp, track_name, False)
```

- [ ] **Step 2: Commit**

```bash
git add stem_splitter/ui/source_panel.py
git commit -m "feat: add tabbed source panel"
```

---

## Task 11: `ui/main_window.py` — wire everything together

**Files:**
- Create: `stem_splitter/ui/main_window.py`

- [ ] **Step 1: Implement `stem_splitter/ui/main_window.py`**

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

    def _on_start_pipeline(self, source: str, track_name: str, is_url: bool):
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
        self._progress.reset()
        self._output.show_results(output_dir)

    def _on_convert_midi(self, stems: list):
        if not stems:
            return
        output_dir = Path(stems[0]).parent
        self._progress.show_midi()
        self._midi_worker = MidiWorker([Path(s) for s in stems], output_dir)
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
        self._progress.reset()
        QMessageBox.critical(self, "Error", message)
```

- [ ] **Step 2: Commit**

```bash
git add stem_splitter/ui/main_window.py
git commit -m "feat: add main window wiring all panels and workers"
```

---

## Task 12: `stem_splitter/main.py` — entry point

**Files:**
- Create: `stem_splitter/main.py`

- [ ] **Step 1: Implement `stem_splitter/main.py`**

```python
import sys
from PyQt6.QtWidgets import QApplication
from stem_splitter.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add stem_splitter/main.py
git commit -m "feat: add app entry point"
```

---

## Task 13: Full test suite and smoke test

- [ ] **Step 1: Run the full test suite**

```bash
pytest -v
```

Expected: All 19 tests pass (6 output, 6 downloader, 4 recorder, 3 separator, 2 midi, 4 worker). Fix any failures before continuing.

- [ ] **Step 2: Launch the app**

```bash
python -m stem_splitter.main
```

Expected: Window opens with three tabs (YouTube URL, Local File, Apple Music).

- [ ] **Step 3: Smoke test — local file**

- Copy a short MP3 (under 1 min) into the project directory
- Select it in the Local File tab and click Start
- Separating... progress bar appears
- On first run Demucs downloads ~1 GB of weights automatically during the Separating step — the bar will hold at 0% until the download finishes, then separation runs. Subsequent runs skip the download.
- Output panel appears listing 6 stem WAVs
- Click Open Folder — Finder opens `~/Documents/music_tracks/<track name>/`
- Verify `vocals.wav`, `drums.wav`, `bass.wav`, `guitar.wav`, `piano.wav`, `other.wav` are present and non-zero bytes

- [ ] **Step 4: Smoke test — MIDI conversion**

- In the output panel, leave all boxes checked except Drums
- Click Convert Selected
- MIDI progress bar appears then disappears
- Verify `vocals.mid`, `bass.mid`, `guitar.mid`, `piano.mid`, `other.mid` appear in the output folder
- Verify `drums.mid` does NOT appear

- [ ] **Step 5: Smoke test — YouTube URL**

- Paste a public YouTube URL into the YouTube URL tab and click Start
- Downloading... bar appears, then Separating... bar
- Output panel shows stems on completion

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "chore: verify full pipeline via smoke test"
```
