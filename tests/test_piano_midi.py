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


def test_convert_piano_to_midi_calls_transcribe_with_correct_dest(tmp_path):
    wav_path = tmp_path / "piano.wav"
    wav_path.write_bytes(b"fake")
    mock_audio = np.zeros(1000, dtype=np.float32)

    with patch("stem_splitter.core.piano_midi.PianoTranscription") as MockT, \
         patch("stem_splitter.core.piano_midi.load_audio", return_value=(mock_audio, 16000)):
        mock_t = MagicMock()
        MockT.return_value = mock_t
        convert_piano_to_midi(wav_path, tmp_path)

    expected_dest = str(tmp_path / "piano.mid")
    mock_t.transcribe.assert_called_once_with(mock_audio, expected_dest)


def test_convert_piano_to_midi_uses_cpu_device(tmp_path):
    wav_path = tmp_path / "piano.wav"
    wav_path.write_bytes(b"fake")
    mock_audio = np.zeros(1000, dtype=np.float32)

    with patch("stem_splitter.core.piano_midi.PianoTranscription") as MockT, \
         patch("stem_splitter.core.piano_midi.load_audio", return_value=(mock_audio, 16000)):
        MockT.return_value = MagicMock()
        convert_piano_to_midi(wav_path, tmp_path)

    MockT.assert_called_once_with(device="cpu", checkpoint_path=None)
