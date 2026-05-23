import subprocess
import sys
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
