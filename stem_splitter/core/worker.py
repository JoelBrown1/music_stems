import tempfile
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from stem_splitter.core.downloader import download_audio
from stem_splitter.core.separator import separate
from stem_splitter.core.output import make_output_dir
from stem_splitter.core.midi import convert_to_midi


class PipelineWorker(QThread):
    progress = pyqtSignal(str, int)   # stage, percent
    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(self, source: str, track_name: str, is_url: bool = False):
        super().__init__()
        self.source = source
        self.track_name = track_name
        self.is_url = is_url

    def run(self):
        try:
            if self.is_url:
                with tempfile.TemporaryDirectory() as tmp:
                    self.progress.emit("Downloading", 0)
                    audio_path = download_audio(self.source, Path(tmp))
                    self.progress.emit("Downloading", 100)
                    output_dir = make_output_dir(self.track_name)
                    self.progress.emit("Separating", 0)
                    separate(audio_path, output_dir)
                    self.progress.emit("Separating", 100)
                    self.finished.emit(output_dir)
            else:
                audio_path = Path(self.source)
                output_dir = make_output_dir(self.track_name)
                self.progress.emit("Separating", 0)
                separate(audio_path, output_dir)
                self.progress.emit("Separating", 100)
                self.finished.emit(output_dir)
        except Exception as e:
            self.error.emit(str(e))


class MidiWorker(QThread):
    progress = pyqtSignal(str, int)   # stem_name, percent
    finished = pyqtSignal()
    error = pyqtSignal(str, str)      # stem_name, message

    def __init__(self, stems: list[Path], output_dir: Path):
        super().__init__()
        self.stems = stems
        self.output_dir = output_dir

    def run(self):
        total = len(self.stems)
        for i, wav_path in enumerate(self.stems):
            try:
                self.progress.emit(wav_path.stem, int(i / total * 100))
                convert_to_midi(wav_path, self.output_dir)
            except Exception as e:
                self.error.emit(wav_path.stem, str(e))
        self.finished.emit()
