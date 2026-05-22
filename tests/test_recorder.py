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
    mock_stream = MagicMock()
    recorder._stream = mock_stream
    with patch("stem_splitter.core.recorder.sf.write") as mock_write:
        dest = tmp_path / "recording.wav"
        recorder.stop(dest)
    mock_stream.stop.assert_called_once()
    mock_stream.close.assert_called_once()
    assert mock_write.called
    assert str(dest) in mock_write.call_args[0][0]

def test_recorder_stop_raises_if_no_frames_recorded(tmp_path):
    recorder = Recorder()
    recorder._stream = MagicMock()
    with pytest.raises(RuntimeError, match="No audio recorded"):
        recorder.stop(tmp_path / "recording.wav")
