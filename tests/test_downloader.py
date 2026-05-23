import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from subprocess import CalledProcessError
from stem_splitter.core.downloader import is_valid_youtube_url, download_audio

def test_valid_youtube_watch_url():
    assert is_valid_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

def test_valid_youtu_be_url():
    assert is_valid_youtube_url("https://youtu.be/dQw4w9WgXcQ") is True

def test_invalid_url_returns_false():
    assert is_valid_youtube_url("https://soundcloud.com/track") is False

def test_empty_url_returns_false():
    assert is_valid_youtube_url("") is False

def test_download_audio_calls_yt_dlp(tmp_path):
    fake_wav = tmp_path / "My Track.wav"
    fake_wav.touch()
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = download_audio("https://www.youtube.com/watch?v=abc", tmp_path)
    args = mock_run.call_args[0][0]
    assert args[0].endswith("yt-dlp")
    assert "-x" in args
    assert "--audio-format" in args
    assert "wav" in args
    assert result == fake_wav

def test_download_audio_raises_if_no_wav_produced(tmp_path):
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with pytest.raises(RuntimeError, match="did not produce a WAV"):
            download_audio("https://www.youtube.com/watch?v=abc", tmp_path)

def test_download_audio_raises_on_yt_dlp_nonzero_exit(tmp_path):
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.side_effect = CalledProcessError(1, "yt-dlp", stderr="Private video")
        with pytest.raises(CalledProcessError):
            download_audio("https://www.youtube.com/watch?v=abc", tmp_path)
