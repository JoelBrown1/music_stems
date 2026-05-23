from pathlib import Path
from piano_transcription_inference import PianoTranscription, load_audio, sample_rate


def convert_piano_to_midi(wav_path: Path, output_dir: Path) -> Path:
    transcriptor = PianoTranscription(device="cpu", checkpoint_path=None)
    audio, _ = load_audio(str(wav_path), sr=sample_rate, mono=True)
    dest = output_dir / "piano.mid"
    transcriptor.inference(audio, str(dest))
    return dest
