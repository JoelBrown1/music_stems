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


def test_volume_scaling(tmp_path):
    data = np.ones((1000, 2), dtype='float32')
    sf.write(str(tmp_path / 'vocals.wav'), data, 44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_volume('vocals', 0.5)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    np.testing.assert_allclose(outdata, 0.5, atol=1e-4)


def test_mute_produces_silence(tmp_path):
    data = np.ones((1000, 2), dtype='float32')
    sf.write(str(tmp_path / 'vocals.wav'), data, 44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_mute('vocals', True)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    np.testing.assert_allclose(outdata, 0.0)


def test_solo_silences_other_stems(tmp_path):
    for stem in ('vocals', 'drums'):
        sf.write(str(tmp_path / f'{stem}.wav'),
                 np.ones((1000, 2), dtype='float32'), 44100)
    engine = PlayerEngine({
        'vocals': tmp_path / 'vocals.wav',
        'drums': tmp_path / 'drums.wav',
    })
    engine.set_solo('vocals', True)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    # only vocals contributes — result is 1.0, not 2.0
    np.testing.assert_allclose(outdata, 1.0, atol=1e-4)


def test_muted_solo_produces_silence(tmp_path):
    data = np.ones((1000, 2), dtype='float32')
    sf.write(str(tmp_path / 'vocals.wav'), data, 44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_solo('vocals', True)
    engine.set_mute('vocals', True)

    outdata = np.zeros((100, 2), dtype='float32')
    engine._mix_chunk(outdata, 100)
    np.testing.assert_allclose(outdata, 0.0)
