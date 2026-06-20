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


def test_seek_updates_position(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(0.5)
    assert abs(engine.position - 0.5) < 0.001


def test_seek_clamps_to_valid_range(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(2.0)
    assert engine.position == 1.0
    engine.seek(-1.0)
    assert engine.position == 0.0


def test_mix_chunk_advances_position(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    outdata = np.zeros((512, 2), dtype='float32')
    engine._mix_chunk(outdata, 512)
    expected = 512 / 44100
    assert abs(engine.position - expected) < 0.001


def test_stop_resets_position(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(0.5)
    engine.stop()
    assert engine.position == 0.0
    assert engine.is_playing is False


def test_loop_wraps_position_at_loop_end(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_loop_start(0.1)
    engine.set_loop_end(0.2)
    engine.set_loop_enabled(True)

    # seek just before loop end
    loop_end_sample = int(0.2 * 44100)
    engine.seek((loop_end_sample - 10) / 44100)

    outdata = np.zeros((512, 2), dtype='float32')
    engine._mix_chunk(outdata, 512)

    # position should have wrapped back to loop_start
    assert engine.position < 0.2
    assert engine.position >= 0.1


def test_loop_disabled_does_not_wrap(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_loop_start(0.1)
    engine.set_loop_end(0.2)
    engine.set_loop_enabled(False)

    engine.seek(0.19)
    outdata = np.zeros((512, 2), dtype='float32')
    engine._mix_chunk(outdata, 512)
    assert engine.position > 0.2


def test_set_loop_swaps_if_start_greater_than_end(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.set_loop_start(0.8)
    engine.set_loop_end(0.2)
    with engine._lock:
        assert engine._loop_start < engine._loop_end


def test_stretch_halves_rate_doubles_length(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    original_len = engine._length
    engine.stretch(0.5)
    # half speed = double length (within 5% tolerance for phase vocoder)
    assert abs(engine._length - original_len * 2) < original_len * 0.05


def test_stretch_preserves_relative_position(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    engine.seek(0.5)
    engine.stretch(0.5)
    assert abs(engine.position - 0.5) < 0.01


def test_stretch_rate_1_restores_original_length(tmp_path):
    _wav(tmp_path / 'vocals.wav', samples=44100)
    engine = PlayerEngine({'vocals': tmp_path / 'vocals.wav'})
    original_len = engine._length
    engine.stretch(0.5)
    assert engine._length != original_len
    engine.stretch(1.0)
    assert engine._length == original_len
