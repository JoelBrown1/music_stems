# tests/test_player.py
import numpy as np
import pytest
import soundfile as sf
from pathlib import Path
from stem_splitter.core.player import PlayerEngine


def _wav(path: Path, samples: int = 1000, sr: int = 44100) -> None:
    """Write a simple stereo WAV file of ones."""
    sf.write(str(path), np.ones((samples, 2), dtype='float32'), sr)


def test_loads_available_stems(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    _wav(tmp_path / 'drums.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav',
                           'drums': tmp_path / 'drums.wav'})
    assert engine._available == {'vocals', 'drums'}


def test_missing_stem_does_not_raise(tmp_path):
    _wav(tmp_path / 'drums.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'missing.wav',
                           'drums': tmp_path / 'drums.wav'})
    assert 'drums' in engine._available
    assert 'vocals' not in engine._available


def test_duration_matches_wav_length(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)  # exactly 1 second
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    assert abs(engine.duration - 1.0) < 0.01


def test_initial_position_is_zero(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    assert engine.position == 0.0


def test_initial_is_playing_false(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    assert engine.is_playing is False
