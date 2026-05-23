from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QCheckBox, QDoubleSpinBox, QPushButton,
)
from PyQt6.QtCore import Qt
from stem_splitter.core.midi_params import MidiParams, DEFAULTS


class MidiParamsWidget(QWidget):
    def __init__(self, stem: str, parent=None):
        super().__init__(parent)
        self._stem = stem
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 4, 4, 8)

        if stem == "piano":
            layout.addWidget(QLabel("Using piano transcription model — no parameters needed."))
            self._reset_btn = None
            return

        if stem == "drums":
            self._sensitivity = self._add_slider(layout, "Sensitivity", 10, 90, int(DEFAULTS["drums"].sensitivity * 100), step=5)
        else:
            d = DEFAULTS[stem]
            self._onset = self._add_slider(layout, "Onset threshold", 10, 90, int(d.onset_threshold * 100), step=5)
            self._frame = self._add_slider(layout, "Frame threshold", 10, 90, int(d.frame_threshold * 100), step=5)
            self._min_length = self._add_slider(layout, "Min note length (ms)", 10, 500, d.minimum_note_length, step=10)

            freq_row = QHBoxLayout()
            freq_row.addWidget(QLabel("Min freq (Hz)"))
            self._min_freq = QDoubleSpinBox()
            self._min_freq.setRange(20.0, 2000.0)
            self._min_freq.setValue(d.minimum_frequency)
            freq_row.addWidget(self._min_freq)
            freq_row.addWidget(QLabel("Max freq (Hz)"))
            self._max_freq = QDoubleSpinBox()
            self._max_freq.setRange(200.0, 20000.0)
            self._max_freq.setValue(d.maximum_frequency)
            freq_row.addWidget(self._max_freq)
            layout.addLayout(freq_row)

            self._min_freq.valueChanged.connect(self._validate_freq)
            self._max_freq.valueChanged.connect(self._validate_freq)

            self._melodia = QCheckBox("Melodia trick")
            self._melodia.setChecked(d.melodia_trick)
            layout.addWidget(self._melodia)

        self._reset_btn = QPushButton("Reset to preset")
        self._reset_btn.clicked.connect(self._reset)
        layout.addWidget(self._reset_btn)

    def _add_slider(self, layout: QVBoxLayout, label: str, min_val: int, max_val: int, value: int, step: int = 1) -> QSlider:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setSingleStep(step)
        slider.setPageStep(step * 2)
        slider.setValue(value)
        val_label = QLabel(str(value))
        val_label.setFixedWidth(36)
        slider.valueChanged.connect(val_label.setNum)
        row.addWidget(slider)
        row.addWidget(val_label)
        layout.addLayout(row)
        return slider

    def _validate_freq(self):
        invalid = self._min_freq.value() >= self._max_freq.value()
        style = "border: 1px solid red;" if invalid else ""
        self._min_freq.setStyleSheet(style)
        self._max_freq.setStyleSheet(style)

    def is_valid(self) -> bool:
        if self._stem in ("piano", "drums"):
            return True
        return self._min_freq.value() < self._max_freq.value()

    def get_params(self) -> MidiParams:
        if self._stem == "piano":
            return DEFAULTS["piano"]
        if self._stem == "drums":
            return MidiParams(sensitivity=self._sensitivity.value() / 100.0)
        return MidiParams(
            onset_threshold=self._onset.value() / 100.0,
            frame_threshold=self._frame.value() / 100.0,
            minimum_note_length=self._min_length.value(),
            minimum_frequency=self._min_freq.value(),
            maximum_frequency=self._max_freq.value(),
            melodia_trick=self._melodia.isChecked(),
        )

    def _reset(self):
        d = DEFAULTS[self._stem]
        if self._stem == "drums":
            self._sensitivity.setValue(int(d.sensitivity * 100))
        elif self._stem != "piano":
            self._onset.setValue(int(d.onset_threshold * 100))
            self._frame.setValue(int(d.frame_threshold * 100))
            self._min_length.setValue(d.minimum_note_length)
            self._min_freq.setValue(d.minimum_frequency)
            self._max_freq.setValue(d.maximum_frequency)
            self._melodia.setChecked(d.melodia_trick)
