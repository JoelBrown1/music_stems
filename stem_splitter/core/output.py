from pathlib import Path

MUSIC_TRACKS_DIR = Path.home() / "Documents" / "music_tracks"
STEMS = ["vocals", "drums", "bass", "guitar", "piano", "other"]

def make_output_dir(track_name: str, base_dir: Path = MUSIC_TRACKS_DIR) -> Path:
    candidate = base_dir / track_name
    if not candidate.exists():
        candidate.mkdir(parents=True)
        return candidate
    n = 2
    while True:
        candidate = base_dir / f"{track_name} ({n})"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
        n += 1

def stem_paths(output_dir: Path) -> dict[str, Path]:
    return {stem: output_dir / f"{stem}.wav" for stem in STEMS}

def midi_path(output_dir: Path, stem: str) -> Path:
    if stem not in STEMS:
        raise ValueError(f"Unknown stem {stem!r}. Must be one of {STEMS}")
    return output_dir / f"{stem}.mid"
