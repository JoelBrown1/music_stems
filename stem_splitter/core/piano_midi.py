from pathlib import Path
import librosa.core.audio as _librosa_audio

# piano_transcription_inference calls resample(y, orig_sr, target_sr) with positional
# args, but librosa >=0.10 made those keyword-only. Wrap to restore compat.
_orig_resample = _librosa_audio.resample
def _resample_compat(y, orig_sr=None, target_sr=None, **kwargs):
    return _orig_resample(y, orig_sr=orig_sr, target_sr=target_sr, **kwargs)
_librosa_audio.resample = _resample_compat

from piano_transcription_inference import PianoTranscription, load_audio, sample_rate


def convert_piano_to_midi(wav_path: Path, output_dir: Path) -> Path:
    transcriptor = PianoTranscription(device="cpu", checkpoint_path=None)
    audio, _ = load_audio(str(wav_path), sr=sample_rate, mono=True)
    dest = output_dir / "piano.mid"
    transcriptor.transcribe(audio, str(dest))
    return dest
