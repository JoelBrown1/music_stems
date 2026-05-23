import numpy as np
import librosa
import pretty_midi
from pathlib import Path

_KICK = 36
_SNARE = 38
_CLOSED_HH = 42
_OPEN_HH = 46
_WINDOW_SEC = 0.05  # 50 ms spectral analysis window


def convert_drums_to_midi(wav_path: Path, output_dir: Path, sensitivity: float = 0.50) -> Path:
    audio, sr = librosa.load(str(wav_path), sr=None, mono=True)

    onset_frames = librosa.onset.onset_detect(
        y=audio, sr=sr, backtrack=True, delta=sensitivity * 0.1
    )
    if len(onset_frames) == 0:
        raise RuntimeError("No drum hits detected — try lowering sensitivity")

    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    window_samples = int(_WINDOW_SEC * sr)

    midi = pretty_midi.PrettyMIDI()
    drum_track = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for t in onset_times:
        start = int(t * sr)
        end = min(start + window_samples, len(audio))
        window = audio[start:end]

        if len(window) < 2:
            centroid = 1000.0
        else:
            S = np.abs(np.fft.rfft(window))
            freqs = np.fft.rfftfreq(len(window), d=1.0 / sr)
            centroid = float(np.sum(freqs * S) / (np.sum(S) + 1e-9))

        if centroid < 200:
            pitch = _KICK
        elif centroid < 800:
            pitch = _SNARE
        elif centroid < 3000:
            pitch = _CLOSED_HH
        else:
            pitch = _OPEN_HH

        note = pretty_midi.Note(
            velocity=100, pitch=pitch, start=float(t), end=float(t) + 0.1
        )
        drum_track.notes.append(note)

    midi.instruments.append(drum_track)
    dest = output_dir / "drums.mid"
    midi.write(str(dest))
    return dest
