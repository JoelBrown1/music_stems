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
