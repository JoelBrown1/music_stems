import numpy as np
from pathlib import Path
import librosa
import pretty_midi
from madmom.features import RNNOnsetProcessor, OnsetPeakPickingProcessor

_KICK = 36
_SNARE = 38
_CLOSED_HH = 42
_OPEN_HH = 46
_NOTE_DURATION_SEC = 0.05
_WINDOW_SEC = 0.04
_VELOCITY_MIN = 40
_VELOCITY_MAX = 127


def _classify_onset(audio: np.ndarray, sr: int, t: float) -> int:
    start = int(t * sr)
    end = min(start + int(_WINDOW_SEC * sr), len(audio))
    window = audio[start:end]
    if len(window) < 4:
        return _SNARE
    S = np.abs(np.fft.rfft(window, n=512))
    freqs = np.fft.rfftfreq(512, d=1.0 / sr)
    eps = 1e-9
    total = np.sum(S) + eps
    kick_ratio = np.sum(S[freqs < 250]) / total
    hh_ratio = np.sum(S[freqs >= 5000]) / total
    centroid = float(np.sum(freqs * S) / total)
    if kick_ratio > 0.3:
        return _KICK
    if hh_ratio > 0.4 or centroid > 5000:
        return _OPEN_HH if centroid > 8000 else _CLOSED_HH
    return _SNARE


def _onset_velocity(audio: np.ndarray, sr: int, t: float) -> int:
    start = int(t * sr)
    end = min(start + int(_WINDOW_SEC * sr), len(audio))
    window = audio[start:end]
    rms = float(np.sqrt(np.mean(window ** 2) + 1e-9))
    velocity = int(_VELOCITY_MIN + min(rms / 0.5, 1.0) * (_VELOCITY_MAX - _VELOCITY_MIN))
    return max(_VELOCITY_MIN, min(_VELOCITY_MAX, velocity))


def convert_drums_to_midi(wav_path: Path, output_dir: Path, sensitivity: float = 0.50) -> Path:
    onset_proc = RNNOnsetProcessor()
    activations = onset_proc(str(wav_path))  # 1D float32 at 100 fps

    threshold = 1.0 - sensitivity
    peak_proc = OnsetPeakPickingProcessor(threshold=threshold, fps=100)
    onset_times = peak_proc(activations)

    if len(onset_times) == 0:
        raise RuntimeError("No drum hits detected — try lowering sensitivity")

    audio, sr = librosa.load(str(wav_path), sr=None, mono=True)

    midi = pretty_midi.PrettyMIDI()
    drum_track = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for t in onset_times:
        pitch = _classify_onset(audio, sr, float(t))
        velocity = _onset_velocity(audio, sr, float(t))
        drum_track.notes.append(pretty_midi.Note(
            velocity=velocity, pitch=pitch,
            start=float(t), end=float(t) + _NOTE_DURATION_SEC,
        ))

    midi.instruments.append(drum_track)
    dest = output_dir / "drums.mid"
    midi.write(str(dest))
    return dest
