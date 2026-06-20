from __future__ import annotations

import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QGroupBox,
)
from PyQt6.QtCore import pyqtSignal
from stem_splitter.core.output import STEMS
from stem_splitter.ui.midi_params_widget import MidiParamsWidget


class OutputPanel(QWidget):
    # Emits list of dicts: [{"stem": str, "wav_path": Path, "params": MidiParams}, ...]
    convert_midi_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output_dir: Path | None = None
        self._checkboxes: dict[str, QCheckBox] = {}
        self._params_widgets: dict[str, MidiParamsWidget] = {}
        self._gear_btns: dict[str, QPushButton] = {}
        self._active_stem: str | None = None

        layout = QVBoxLayout(self)
        self._path_label = QLabel("")
        layout.addWidget(self._path_label)

        midi_box = QGroupBox("Convert to MIDI")
        midi_layout = QVBoxLayout(midi_box)

        for stem in STEMS:
            row = QHBoxLayout()

            cb = QCheckBox(stem)
            cb.setChecked(True)
            self._checkboxes[stem] = cb
            row.addWidget(cb)
            row.addStretch()

            gear_btn = QPushButton("⚙")
            gear_btn.setFixedWidth(30)
            gear_btn.setCheckable(True)
            gear_btn.clicked.connect(lambda _checked, s=stem: self._on_gear(s))
            self._gear_btns[stem] = gear_btn
            row.addWidget(gear_btn)

            midi_layout.addLayout(row)

            params_widget = MidiParamsWidget(stem)
            params_widget.setVisible(False)
            self._params_widgets[stem] = params_widget
            midi_layout.addWidget(params_widget)

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

    def _on_gear(self, stem: str):
        if self._active_stem == stem:
            self._params_widgets[stem].setVisible(False)
            self._gear_btns[stem].setChecked(False)
            self._active_stem = None
        else:
            if self._active_stem is not None:
                self._params_widgets[self._active_stem].setVisible(False)
                self._gear_btns[self._active_stem].setChecked(False)
            self._params_widgets[stem].setVisible(True)
            self._active_stem = stem

    def show_results(self, output_dir: Path):
        self._output_dir = output_dir
        self._path_label.setText(str(output_dir))
        self.setVisible(True)

    def _on_convert(self):
        if not self._output_dir:
            return
        invalid = [
            stem for stem, cb in self._checkboxes.items()
            if cb.isChecked() and not self._params_widgets[stem].is_valid()
        ]
        if invalid:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Invalid Parameters",
                f"Fix frequency range (min must be < max) for: {', '.join(invalid)}",
            )
            return
        selected = [
            {
                "stem": stem,
                "wav_path": self._output_dir / f"{stem}.wav",
                "params": self._params_widgets[stem].get_params(),
            }
            for stem, cb in self._checkboxes.items()
            if cb.isChecked()
        ]
        self.convert_midi_requested.emit(selected)

    def _on_open_folder(self):
        if self._output_dir:
            subprocess.run(["open", str(self._output_dir)])
