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
