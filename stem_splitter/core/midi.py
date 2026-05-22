from pathlib import Path
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH

def convert_to_midi(wav_path: Path, output_dir: Path) -> Path:
    predict_and_save(
        [str(wav_path)],
        str(output_dir),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
    )
    midi_files = list(output_dir.glob(f"{wav_path.stem}*.mid"))
    if not midi_files:
        raise RuntimeError(f"Basic Pitch did not produce a MIDI file for {wav_path.name}")
    dest = output_dir / f"{wav_path.stem}.mid"
    midi_files[0].rename(dest)
    return dest
