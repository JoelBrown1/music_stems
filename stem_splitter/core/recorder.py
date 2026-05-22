import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path

BLACKHOLE_NAME = "BlackHole 2ch"
SAMPLE_RATE = 44100

def _blackhole_device_index() -> int | None:
    for i, dev in enumerate(sd.query_devices()):
        if BLACKHOLE_NAME in dev["name"] and dev["max_input_channels"] > 0:
            return i
    return None

def is_blackhole_available() -> bool:
    return _blackhole_device_index() is not None

class Recorder:
    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        device = _blackhole_device_index()
        if device is None:
            raise RuntimeError("BlackHole 2ch not found")
        self._frames = []
        self._stream = sd.InputStream(
            device=device, samplerate=SAMPLE_RATE, channels=2,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time, status):
        self._frames.append(indata.copy())

    def stop(self, dest_path: Path) -> Path:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._frames:
            raise RuntimeError("No audio recorded — stop() called before any frames were captured")
        audio = np.concatenate(self._frames, axis=0)
        sf.write(str(dest_path), audio, SAMPLE_RATE)
        return dest_path
