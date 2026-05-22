import os
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLineEdit, QPushButton, QLabel, QFileDialog,
)
from PyQt6.QtCore import pyqtSignal
from stem_splitter.core.downloader import is_valid_youtube_url
from stem_splitter.core.recorder import is_blackhole_available, Recorder


class SourcePanel(QWidget):
    start_pipeline = pyqtSignal(str, str, bool)   # source, track_name, is_url

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recorder: Recorder | None = None

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._make_youtube_tab(), "YouTube URL")
        tabs.addTab(self._make_local_tab(), "Local File")
        tabs.addTab(self._make_apple_music_tab(), "Apple Music")
        layout.addWidget(tabs)

    def _make_youtube_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("YouTube URL or paste link here")
        self._url_start_btn = QPushButton("Start")
        self._url_start_btn.clicked.connect(self._on_url_start)
        row.addWidget(self._url_input)
        row.addWidget(self._url_start_btn)
        self._url_error = QLabel("")
        self._url_error.setStyleSheet("color: red;")
        layout.addLayout(row)
        layout.addWidget(self._url_error)
        return w

    def _on_url_start(self):
        url = self._url_input.text().strip()
        if not is_valid_youtube_url(url):
            self._url_error.setText("Invalid YouTube URL")
            return
        self._url_error.setText("")
        track_name = url.split("v=")[-1] if "v=" in url else url.split("/")[-1]
        self.start_pipeline.emit(url, track_name, True)

    def _make_local_tab(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("File path")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._on_browse)
        start = QPushButton("Start")
        start.clicked.connect(self._on_file_start)
        row.addWidget(self._file_input)
        row.addWidget(browse)
        row.addWidget(start)
        return w

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select audio file", "",
            "Audio Files (*.mp3 *.wav *.flac *.m4a)"
        )
        if path:
            self._file_input.setText(path)

    def _on_file_start(self):
        path = self._file_input.text().strip()
        if not path:
            return
        self.start_pipeline.emit(path, Path(path).stem, False)

    def _make_apple_music_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        if not is_blackhole_available():
            layout.addWidget(QLabel(
                "⚠ BlackHole 2ch not detected.\n\n"
                "Install BlackHole and create a Multi-Output Device in\n"
                "macOS Audio MIDI Setup so audio routes to both your\n"
                "speakers and BlackHole simultaneously.\n\n"
                "Download: https://existential.audio/blackhole/"
            ))
            return w

        layout.addWidget(QLabel("1. Play the track in Apple Music\n2. Press Record when ready"))

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Track name:"))
        self._track_name_input = QLineEdit()
        name_row.addWidget(self._track_name_input)
        layout.addLayout(name_row)

        btn_row = QHBoxLayout()
        self._record_btn = QPushButton("● Record")
        self._record_btn.clicked.connect(self._on_record)
        self._stop_btn = QPushButton("■ Stop & Split")
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._record_btn)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)
        return w

    def _on_record(self):
        self._recorder = Recorder()
        self._recorder.start()
        self._record_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _on_stop(self):
        if not self._recorder:
            return
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            self._recorder.stop(Path(tmp))
        except RuntimeError as exc:
            self._recorder = None
            self._record_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Recording Error", str(exc))
            return
        self._recorder = None
        self._record_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        track_name = self._track_name_input.text().strip() or "Apple Music Recording"
        self.start_pipeline.emit(tmp, track_name, False)
