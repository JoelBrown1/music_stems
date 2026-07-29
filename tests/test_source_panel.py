from stem_splitter.ui.source_panel import _sanitize_track_name, _build_pipeline_args
from stem_splitter.core.downloader import SearchResult


def test_sanitize_track_name_replaces_slash():
    assert _sanitize_track_name("AC/DC - Back In Black") == "AC_DC - Back In Black"


def test_sanitize_track_name_replaces_multiple_unsafe_chars():
    assert _sanitize_track_name("Weird: Title?") == "Weird_ Title_"


def test_sanitize_track_name_strips_surrounding_whitespace():
    assert _sanitize_track_name("  Padded Title  ") == "Padded Title"


def test_build_pipeline_args_returns_expected_tuple():
    result = SearchResult(
        video_id="abc123", title="AC/DC - Back In Black",
        channel="Sony Music", duration_seconds=255,
        thumbnail_url="https://i.ytimg.com/vi/abc123/hq720.jpg",
        url="https://www.youtube.com/watch?v=abc123",
    )
    assert _build_pipeline_args(result) == (
        "https://www.youtube.com/watch?v=abc123", "AC_DC - Back In Black", True,
    )
