import subprocess
from pathlib import Path
from stem_splitter.core.output import STEMS

MODEL = "htdemucs_6s"

def separate(audio_path: Path, output_dir: Path) -> dict[str, Path]:
    subprocess.run(
        ["python", "-m", "demucs", "-n", MODEL, "-o", str(output_dir), str(audio_path)],
        check=True,
    )
    track_name = audio_path.stem
    demucs_dir = output_dir / MODEL / track_name
    result = {}
    for stem in STEMS:
        src = demucs_dir / f"{stem}.wav"
        dest = output_dir / f"{stem}.wav"
        src.rename(dest)
        result[stem] = dest
    return result
