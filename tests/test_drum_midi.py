import numpy as np
import soundfile as sf
import pytest
from pathlib import Path
from stem_splitter.core.drum_midi import convert_drums_to_midi


@pytest.fixture
def drum_wav(tmp_path):
    sr = 22050
    audio = np.zeros(sr * 4, dtype=np.float32)
    # Four transient impulses at 0.5 s intervals
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
