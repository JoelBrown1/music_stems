import numpy as np
import soundfile as sf
import pretty_midi
import pytest
from pathlib import Path
from stem_splitter.core.drum_midi import convert_drums_to_midi


@pytest.fixture
def drum_wav(tmp_path):
    sr = 22050
    audio = np.zeros(sr * 4, dtype=np.float32)
    for t in [0.5, 1.0, 1.5, 2.0]:
        idx = int(t * sr)
        audio[idx] = 1.0
    path = tmp_path / "drums.wav"
    sf.write(str(path), audio, sr)
    return path


def test_convert_drums_to_midi_returns_correct_path_and_creates_file(drum_wav, tmp_path):
    result = convert_drums_to_midi(drum_wav, tmp_path, sensitivity=0.5)
    assert result == tmp_path / "drums.mid"
    assert result.exists()


def test_convert_drums_to_midi_produces_drum_track_with_notes(drum_wav, tmp_path):
    result = convert_drums_to_midi(drum_wav, tmp_path, sensitivity=0.5)
    midi = pretty_midi.PrettyMIDI(str(result))
    assert len(midi.instruments) == 1
    instrument = midi.instruments[0]
    assert instrument.is_drum is True
    assert len(instrument.notes) > 0
    for note in instrument.notes:
        assert note.velocity == 100
        assert note.pitch in (36, 38, 42, 46)


def test_convert_drums_to_midi_silent_wav_raises(tmp_path):
    sr = 22050
    audio = np.zeros(sr * 2, dtype=np.float32)
    wav_path = tmp_path / "silence.wav"
    sf.write(str(wav_path), audio, sr)
    with pytest.raises(RuntimeError, match="No drum hits detected"):
        convert_drums_to_midi(wav_path, tmp_path, sensitivity=0.5)
