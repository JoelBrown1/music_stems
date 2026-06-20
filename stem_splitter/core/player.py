import threading
import numpy as np
import soundfile as sf
import librosa
import sounddevice as sd
from pathlib import Path


class PlayerEngine:
    def __init__(self, stem_paths: dict[str, Path]) -> None:
        self._lock = threading.Lock()
        self._arrays: dict[str, np.ndarray] = {}
        self._available: set[str] = set()
        self._sample_rate: int = 44100
        self._length: int = 0
        self._position: int = 0
        self._is_playing: bool = False
        self._stream: sd.OutputStream | None = None

        self._volumes: dict[str, float] = {}
        self._mutes: dict[str, bool] = {}
        self._solos: dict[str, bool] = {}
        self._loop_enabled: bool = False
        self._loop_start: int = 0
        self._loop_end: int = 0

        self._load_stems(stem_paths)

    def _load_stems(self, stem_paths: dict[str, Path]) -> None:
        raw: dict[str, tuple[np.ndarray, int]] = {}
        for stem, path in stem_paths.items():
            if not path.exists():
                continue
            data, sr = sf.read(str(path), dtype='float32', always_2d=True)
            raw[stem] = (data, sr)
            self._available.add(stem)

        if not raw:
            return

        target_sr = next(iter(raw.values()))[1]
        self._sample_rate = target_sr

        for stem, (data, sr) in raw.items():
            if sr != target_sr:
                resampled = np.stack([
                    librosa.resample(data[:, ch], orig_sr=sr, target_sr=target_sr)
                    for ch in range(data.shape[1])
                ], axis=1).astype('float32')
                self._arrays[stem] = resampled
            else:
                self._arrays[stem] = data
            self._volumes[stem] = 1.0
            self._mutes[stem] = False
            self._solos[stem] = False

        self._length = max(a.shape[0] for a in self._arrays.values())
        self._loop_end = self._length

    def set_volume(self, stem: str, value: float) -> None:
        self._volumes[stem] = max(0.0, min(1.0, value))

    def set_mute(self, stem: str, muted: bool) -> None:
        self._mutes[stem] = muted

    def set_solo(self, stem: str, soloed: bool) -> None:
        self._solos[stem] = soloed

    def _mix_chunk(self, outdata: np.ndarray, frames: int) -> None:
        outdata[:] = 0.0

        with self._lock:
            arrays = self._arrays
            pos = self._position
            loop_enabled = self._loop_enabled
            loop_start = self._loop_start
            loop_end = self._loop_end
            total_len = self._length
            any_solo = any(self._solos.values())

        for stem, arr in arrays.items():
            if self._mutes.get(stem, False):
                continue
            if any_solo and not self._solos.get(stem, False):
                continue
            end = min(pos + frames, arr.shape[0])
            if end <= pos:
                continue
            chunk = arr[pos:end] * self._volumes.get(stem, 1.0)
            outdata[:chunk.shape[0]] += chunk

        with self._lock:
            new_pos = pos + frames
            if loop_enabled and loop_end > loop_start and new_pos >= loop_end:
                new_pos = loop_start
            elif not loop_enabled and new_pos >= total_len:
                new_pos = total_len
                self._is_playing = False
            self._position = new_pos

    @property
    def position(self) -> float:
        with self._lock:
            return self._position / self._length if self._length > 0 else 0.0

    @property
    def duration(self) -> float:
        with self._lock:
            return self._length / self._sample_rate if self._sample_rate > 0 else 0.0

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._is_playing
