import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from subprocess import CalledProcessError
from stem_splitter.core.downloader import (
    is_valid_youtube_url, download_audio, SearchResult, search_youtube,
)

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

_SEARCH_STDOUT = (
    '{"id": "abc123", "title": "Song One", "channel": "Artist A", '
    '"duration": 215.0, "thumbnails": [{"url": "https://i.ytimg.com/vi/abc123/default.jpg"}, '
    '{"url": "https://i.ytimg.com/vi/abc123/hq720.jpg"}], '
    '"url": "https://www.youtube.com/watch?v=abc123"}\n'
    '{"id": "def456", "title": "Song Two", "channel": "Artist B", '
    '"duration": 180.0, "thumbnails": [{"url": "https://i.ytimg.com/vi/def456/default.jpg"}], '
    '"url": "https://www.youtube.com/watch?v=def456"}\n'
)

def test_search_youtube_calls_yt_dlp_with_correct_args():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        search_youtube("some query", max_results=5)
    args = mock_run.call_args[0][0]
    assert args[0].endswith("yt-dlp")
    assert args[1] == "ytsearch5:some query"
    assert "--dump-json" in args
    assert "--flat-playlist" in args
    assert "--skip-download" in args

def test_search_youtube_parses_results():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_SEARCH_STDOUT, stderr="")
        results = search_youtube("some query")
    assert results == [
        SearchResult(
            video_id="abc123", title="Song One", channel="Artist A",
            duration_seconds=215, thumbnail_url="https://i.ytimg.com/vi/abc123/hq720.jpg",
            url="https://www.youtube.com/watch?v=abc123",
        ),
        SearchResult(
            video_id="def456", title="Song Two", channel="Artist B",
            duration_seconds=180, thumbnail_url="https://i.ytimg.com/vi/def456/default.jpg",
            url="https://www.youtube.com/watch?v=def456",
        ),
    ]

def test_search_youtube_returns_empty_list_for_no_results():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert search_youtube("nonsense query") == []

def test_search_youtube_raises_on_yt_dlp_failure():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.side_effect = CalledProcessError(1, "yt-dlp", stderr="Network error")
        with pytest.raises(CalledProcessError):
            search_youtube("some query")
