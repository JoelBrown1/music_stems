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

    @property
    def position(self) -> float:
        with self._lock:
            return self._position / self._length if self._length > 0 else 0.0

    @property
    def duration(self) -> float:
        return self._length / self._sample_rate if self._sample_rate > 0 else 0.0

    @property
    def is_playing(self) -> bool:
        return self._is_playing
