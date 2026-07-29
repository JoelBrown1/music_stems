import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_BIN_DIR = Path(sys.executable).parent
_YT_DLP = str(_BIN_DIR / "yt-dlp")

def is_valid_youtube_url(url: str) -> bool:
    return "youtube.com/watch" in url or "youtu.be/" in url

def download_audio(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_YT_DLP, "-x", "--audio-format", "wav",
         "-o", str(dest_dir / "%(title)s.%(ext)s"), url],
        capture_output=True, text=True, check=True,
    )
    wav_files = list(dest_dir.glob("*.wav"))
    if not wav_files:
        raise RuntimeError(f"yt-dlp did not produce a WAV file for {url!r}")
    return wav_files[0]

@dataclass
class SearchResult:
    video_id: str
    title: str
    channel: str
    duration_seconds: int
    thumbnail_url: str
    url: str

def search_youtube(query: str, max_results: int = 5) -> list[SearchResult]:
    result = subprocess.run(
        [_YT_DLP, f"ytsearch{max_results}:{query}",
         "--dump-json", "--flat-playlist", "--skip-download"],
        capture_output=True, text=True, check=True,
    )
    results = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        entry = json.loads(line)
        thumbnails = entry.get("thumbnails") or []
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else ""
        video_id = entry["id"]
        results.append(SearchResult(
            video_id=video_id,
            title=entry.get("title", ""),
            channel=entry.get("channel") or entry.get("uploader") or "",
            duration_seconds=int(entry.get("duration") or 0),
            thumbnail_url=thumbnail_url,
            url=entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        ))
    return results
