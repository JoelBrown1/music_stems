import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from stem_splitter.core.separator import separate, MODEL
from stem_splitter.core.output import STEMS

def _make_demucs_output(tmp_path, track_stem):
    demucs_dir = tmp_path / MODEL / track_stem
    demucs_dir.mkdir(parents=True)
    for stem in STEMS:
        (demucs_dir / f"{stem}.wav").touch()

def test_separate_calls_demucs(tmp_path):
    audio = tmp_path / "track.wav"
    audio.touch()
    _make_demucs_output(tmp_path, "track")
    with patch("stem_splitter.core.separator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        separate(audio, tmp_path)
    args = mock_run.call_args[0][0]
    assert "demucs" in " ".join(args)
    assert MODEL in args

def test_separate_returns_stem_paths(tmp_path):
    audio = tmp_path / "track.wav"
    audio.touch()
    _make_demucs_output(tmp_path, "track")
    with patch("stem_splitter.core.separator.subprocess.run"):
        result = separate(audio, tmp_path)
    assert set(result.keys()) == set(STEMS)
    for stem, path in result.items():
        assert path == tmp_path / f"{stem}.wav"
        assert path.exists()

def test_separate_raises_on_demucs_failure(tmp_path):
    audio = tmp_path / "track.wav"
    audio.touch()
    with patch("stem_splitter.core.separator.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("demucs failed")
        with pytest.raises(Exception, match="demucs failed"):
            separate(audio, tmp_path)
