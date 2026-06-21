from __future__ import annotations

from pathlib import Path
from stem_splitter.core.output import STEMS, MUSIC_TRACKS_DIR


def _has_any_stem(path: Path) -> bool:
    return any((path / f"{stem}.wav").exists() for stem in STEMS)


def _find_stem_dirs(base: Path) -> list[Path]:
    if not base.exists():
        return []
    dirs = [d for d in base.iterdir() if d.is_dir() and _has_any_stem(d)]
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs
