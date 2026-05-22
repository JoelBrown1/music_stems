from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._download_label = QLabel("Downloading...")
        self._download_bar = QProgressBar()
        self._download_bar.setRange(0, 100)

        self._separate_label = QLabel("Separating...")
        self._separate_bar = QProgressBar()
        self._separate_bar.setRange(0, 100)

        self._midi_label = QLabel("Converting to MIDI...")
        self._midi_bar = QProgressBar()
        self._midi_bar.setRange(0, 100)

        for w in [self._download_label, self._download_bar,
                  self._separate_label, self._separate_bar,
                  self._midi_label, self._midi_bar]:
            layout.addWidget(w)

        self.reset()

    def reset(self):
        self.setVisible(False)

    def show_download(self):
        self.setVisible(True)
        self._download_label.setVisible(True)
        self._download_bar.setVisible(True)
        self._download_bar.setValue(0)
        self._separate_label.setVisible(False)
        self._separate_bar.setVisible(False)
        self._midi_label.setVisible(False)
        self._midi_bar.setVisible(False)

    def show_separate(self):
        self.setVisible(True)
        self._download_label.setVisible(False)
        self._download_bar.setVisible(False)
        self._separate_label.setVisible(True)
        self._separate_bar.setVisible(True)
        self._separate_bar.setValue(0)
        self._midi_label.setVisible(False)
        self._midi_bar.setVisible(False)

    def show_midi(self):
        self.setVisible(True)
        self._download_label.setVisible(False)
        self._download_bar.setVisible(False)
        self._separate_label.setVisible(False)
        self._separate_bar.setVisible(False)
        self._midi_label.setVisible(True)
        self._midi_bar.setVisible(True)
        self._midi_bar.setValue(0)

    def update_progress(self, stage: str, value: int):
        if stage == "Downloading":
            self._download_bar.setValue(value)
        elif stage == "Separating":
            self._separate_bar.setValue(value)
        else:
            self._midi_bar.setValue(value)
