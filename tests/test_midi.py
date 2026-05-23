import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from stem_splitter.core.midi import convert_stem_to_midi
from stem_splitter.core.midi_params import MidiParams, DEFAULTS


def test_routing_drums_calls_drum_engine(tmp_path):
    wav = tmp_path / "drums.wav"
    wav.touch()
    with patch("stem_splitter.core.midi.convert_drums_to_midi", return_value=tmp_path / "drums.mid") as mock_drum:
        convert_stem_to_midi("drums", wav, tmp_path, DEFAULTS["drums"])
    mock_drum.assert_called_once_with(wav, tmp_path, DEFAULTS["drums"].sensitivity)


def test_routing_piano_calls_piano_engine(tmp_path):
    wav = tmp_path / "piano.wav"
    wav.touch()
    with patch("stem_splitter.core.midi.convert_piano_to_midi", return_value=tmp_path / "piano.mid") as mock_piano:
        convert_stem_to_midi("piano", wav, tmp_path, DEFAULTS["piano"])
    mock_piano.assert_called_once_with(wav, tmp_path)


def test_routing_vocals_calls_basic_pitch(tmp_path):
    wav = tmp_path / "vocals.wav"
    wav.touch()

    def fake_predict(audio_paths, output_dir, **kwargs):
        Path(output_dir, "vocals_basic_pitch.mid").touch()

    with patch("stem_splitter.core.midi.predict_and_save", side_effect=fake_predict):
        result = convert_stem_to_midi("vocals", wav, tmp_path, DEFAULTS["vocals"])

    assert result == tmp_path / "vocals.mid"
    assert result.exists()


def test_routing_basic_pitch_passes_params(tmp_path):
    wav = tmp_path / "bass.wav"
    wav.touch()
    params = DEFAULTS["bass"]

    def fake_predict(audio_paths, output_dir, **kwargs):
        Path(output_dir, "bass_basic_pitch.mid").touch()

    with patch("stem_splitter.core.midi.predict_and_save", side_effect=fake_predict) as mock_bp:
        convert_stem_to_midi("bass", wav, tmp_path, params)

    call_kwargs = mock_bp.call_args.kwargs
    assert call_kwargs["onset_threshold"] == params.onset_threshold
    assert call_kwargs["frame_threshold"] == params.frame_threshold
    assert call_kwargs["minimum_note_length"] == params.minimum_note_length
    assert call_kwargs["minimum_frequency"] == params.minimum_frequency
    assert call_kwargs["maximum_frequency"] == params.maximum_frequency
    assert call_kwargs["melodia_trick"] == params.melodia_trick


def test_routing_basic_pitch_raises_if_no_output(tmp_path):
    wav = tmp_path / "guitar.wav"
    wav.touch()
    with patch("stem_splitter.core.midi.predict_and_save"):
        with pytest.raises(RuntimeError, match="did not produce a MIDI"):
            convert_stem_to_midi("guitar", wav, tmp_path, DEFAULTS["guitar"])
