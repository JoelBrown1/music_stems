import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QGroupBox, QGridLayout,
)
from PyQt6.QtCore import pyqtSignal
from stem_splitter.core.output import STEMS


class OutputPanel(QWidget):
    convert_midi_requested = pyqtSignal(list)   # list[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output_dir: Path | None = None
        self._checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        self._path_label = QLabel("")
        layout.addWidget(self._path_label)

        midi_box = QGroupBox("Convert to MIDI")
        grid = QGridLayout(midi_box)
        for i, stem in enumerate(STEMS):
            cb = QCheckBox(stem)
            cb.setChecked(stem != "drums")
            if stem == "drums":
                cb.setToolTip(
                    "Drum-to-MIDI transcription is unreliable — results may be inaccurate."
                )
            self._checkboxes[stem] = cb
            grid.addWidget(cb, i // 3, i % 3)
        layout.addWidget(midi_box)

        buttons = QHBoxLayout()
        self._convert_btn = QPushButton("Convert Selected")
        self._convert_btn.clicked.connect(self._on_convert)
        self._open_btn = QPushButton("Open Folder")
        self._open_btn.clicked.connect(self._on_open_folder)
        buttons.addWidget(self._convert_btn)
        buttons.addWidget(self._open_btn)
        layout.addLayout(buttons)

        self.setVisible(False)

    def show_results(self, output_dir: Path):
        self._output_dir = output_dir
        self._path_label.setText(str(output_dir))
        self.setVisible(True)

    def _on_convert(self):
        if not self._output_dir:
            return
        selected = [
            self._output_dir / f"{stem}.wav"
            for stem, cb in self._checkboxes.items()
            if cb.isChecked()
        ]
        self.convert_midi_requested.emit(selected)

    def _on_open_folder(self):
        if self._output_dir:
            subprocess.run(["open", str(self._output_dir)])
