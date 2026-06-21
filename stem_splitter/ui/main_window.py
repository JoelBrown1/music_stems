from __future__ import annotations

from pathlib import Path
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QMessageBox, QPushButton
from stem_splitter.ui.source_panel import SourcePanel
from stem_splitter.ui.progress_panel import ProgressPanel
from stem_splitter.ui.output_panel import OutputPanel
from stem_splitter.ui.player_window import PlayerWindow
from stem_splitter.ui.load_stems_dialog import LoadStemsDialog
from stem_splitter.core.worker import PipelineWorker, MidiWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stem Splitter")
        self.setMinimumWidth(600)
        self._worker: PipelineWorker | None = None
        self._midi_worker: MidiWorker | None = None
        self._player: PlayerWindow | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._source = SourcePanel()
        self._progress = ProgressPanel()
        self._output = OutputPanel()

        layout.addWidget(self._source)
        layout.addWidget(self._progress)
        layout.addWidget(self._output)

        self._source.start_pipeline.connect(self._on_start_pipeline)
        self._output.convert_midi_requested.connect(self._on_convert_midi)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        open_stems_action = file_menu.addAction("Open Stems…")
        open_stems_action.setShortcut("Ctrl+O")
        open_stems_action.triggered.connect(self._open_load_stems_dialog)

        open_btn = QPushButton("Open Stems…")
        open_btn.clicked.connect(self._open_load_stems_dialog)
        layout.addWidget(open_btn)

    def _set_pipeline_running(self, running: bool):
        self._source.setEnabled(not running)

    def _on_start_pipeline(self, source: str, track_name: str, is_url: bool):
        self._set_pipeline_running(True)
        self._output.setVisible(False)
        if is_url:
            self._progress.show_download()
        else:
            self._progress.show_separate()
        self._worker = PipelineWorker(source, track_name, is_url)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_pipeline_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, stage: str, value: int):
        if stage == "Separating":
            self._progress.show_separate()
        self._progress.update_progress(stage, value)

    def _on_pipeline_finished(self, output_dir: Path):
        self._set_pipeline_running(False)
        self._progress.reset()
        self._output.show_results(output_dir)
        if self._player is not None:
            self._player.close()
        self._player = PlayerWindow(output_dir, parent=self)
        self._player.show()

    def _on_convert_midi(self, stems: list):
        if not stems:
            return
        output_dir = stems[0]["wav_path"].parent
        self._progress.show_midi()
        self._midi_worker = MidiWorker(stems, output_dir)
        self._midi_worker.progress.connect(
            lambda stem, pct: self._progress.update_progress(stem, pct)
        )
        self._midi_worker.finished.connect(self._progress.reset)
        self._midi_worker.error.connect(
            lambda stem, msg: QMessageBox.warning(
                self, "MIDI Error", f"Failed to convert {stem}: {msg}"
            )
        )
        self._midi_worker.start()

    def _open_load_stems_dialog(self) -> None:
        dlg = LoadStemsDialog(parent=self)
        if dlg.exec() and dlg.selected_dir:
            if self._player is not None:
                self._player.close()
            self._player = PlayerWindow(dlg.selected_dir, parent=self)
            self._player.show()

    def _on_error(self, message: str):
        self._set_pipeline_running(False)
        self._progress.reset()
        if self._output._output_dir is not None:
            self._output.setVisible(True)
        QMessageBox.critical(self, "Error", message)
