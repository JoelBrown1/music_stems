from pathlib import Path
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
from stem_splitter.core.midi_params import MidiParams
from stem_splitter.core.drum_midi import convert_drums_to_midi
from stem_splitter.core.piano_midi import convert_piano_to_midi


def convert_stem_to_midi(stem: str, wav_path: Path, output_dir: Path, params: MidiParams) -> Path:
    if stem == "drums":
        return convert_drums_to_midi(wav_path, output_dir, params.sensitivity)
    if stem == "piano":
        return convert_piano_to_midi(wav_path, output_dir)
    return _convert_with_basic_pitch(wav_path, output_dir, params)


# Backward-compatible shim for worker.py until Task 6 updates MidiWorker.
def convert_to_midi(wav_path: Path, output_dir: Path) -> Path:
    return _convert_with_basic_pitch(wav_path, output_dir, MidiParams())


def _convert_with_basic_pitch(wav_path: Path, output_dir: Path, params: MidiParams) -> Path:
    predict_and_save(
        [str(wav_path)],
        str(output_dir),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=params.onset_threshold,
        frame_threshold=params.frame_threshold,
        minimum_note_length=params.minimum_note_length,
        minimum_frequency=params.minimum_frequency,
        maximum_frequency=params.maximum_frequency,
        melodia_trick=params.melodia_trick,
    )
    midi_files = list(output_dir.glob(f"{wav_path.stem}*.mid"))
    if not midi_files:
        raise RuntimeError(f"Basic Pitch did not produce a MIDI file for {wav_path.name}")
    dest = output_dir / f"{wav_path.stem}.mid"
    midi_files[0].rename(dest)
    return dest
