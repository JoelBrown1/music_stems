import numpy as np
import pytest
import pretty_midi
from unittest.mock import patch
from stem_splitter.core.drum_midi import convert_drums_to_midi, _classify_onset, _onset_velocity

_KICK = 36
_SNARE = 38
_CLOSED_HH = 42
_OPEN_HH = 46
SR = 22050


def _sine(freq, duration=0.04, amplitude=0.8):
    t = np.linspace(0, duration, int(duration * SR), endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * amplitude).astype(np.float32)


def test_classify_kick():
    assert _classify_onset(_sine(80), SR, 0.0) == _KICK


def test_classify_hihat():
    assert _classify_onset(_sine(8000), SR, 0.0) in (_CLOSED_HH, _OPEN_HH)


def test_classify_snare():
    assert _classify_onset(_sine(1000), SR, 0.0) == _SNARE


def test_onset_velocity_scales_with_amplitude():
    quiet = np.ones(1000, dtype=np.float32) * 0.05
    loud = np.ones(1000, dtype=np.float32) * 0.5
    v_quiet = _onset_velocity(quiet, SR, 0.0)
    v_loud = _onset_velocity(loud, SR, 0.0)
    assert v_quiet < v_loud
    assert 40 <= v_quiet <= 127
    assert 40 <= v_loud <= 127


@patch("stem_splitter.core.drum_midi.RNNOnsetProcessor")
@patch("stem_splitter.core.drum_midi.OnsetPeakPickingProcessor")
@patch("stem_splitter.core.drum_midi.librosa.load")
def test_no_onsets_raises(mock_load, MockPeak, MockRNN, tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    MockRNN.return_value.return_value = np.zeros(200, dtype=np.float32)
    MockPeak.return_value.return_value = np.array([])
    mock_load.return_value = (np.zeros(1000, dtype=np.float32), SR)
    with pytest.raises(RuntimeError, match="No drum hits detected"):
        convert_drums_to_midi(wav, tmp_path)


@patch("stem_splitter.core.drum_midi.RNNOnsetProcessor")
@patch("stem_splitter.core.drum_midi.OnsetPeakPickingProcessor")
@patch("stem_splitter.core.drum_midi.librosa.load")
def test_midi_output_is_valid_drum_track(mock_load, MockPeak, MockRNN, tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    MockRNN.return_value.return_value = np.zeros(200, dtype=np.float32)
    MockPeak.return_value.return_value = np.array([0.25, 0.75])
    mock_load.return_value = (np.zeros(int(SR * 2), dtype=np.float32), SR)
    result = convert_drums_to_midi(wav, tmp_path)
    assert result == tmp_path / "drums.mid"
    assert result.exists()
    midi = pretty_midi.PrettyMIDI(str(result))
    assert len(midi.instruments) == 1
    assert midi.instruments[0].is_drum is True
    assert len(midi.instruments[0].notes) == 2
