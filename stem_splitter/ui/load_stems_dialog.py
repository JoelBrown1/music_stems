from __future__ import annotations

from pathlib import Path
from stem_splitter.core.output import STEMS, MUSIC_TRACKS_DIR
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QDialogButtonBox, QFileDialog, QMessageBox,
)


def _has_any_stem(path: Path) -> bool:
    return any((path / f"{stem}.wav").exists() for stem in STEMS)


def _find_stem_dirs(base: Path) -> list[Path]:
    if not base.exists():
        return []
    dirs = [d for d in base.iterdir() if d.is_dir() and _has_any_stem(d)]
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs


class LoadStemsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Stems")
        self.setMinimumWidth(360)
        self.selected_dir: Path | None = None

        layout = QVBoxLayout(self)
        self._dirs = _find_stem_dirs(MUSIC_TRACKS_DIR)

        if self._dirs:
            layout.addWidget(QLabel("Saved tracks:"))
            self._combo = QComboBox()
            for d in self._dirs:
                self._combo.addItem(d.name, userData=d)
            layout.addWidget(self._combo)
        else:
            self._combo = None
            layout.addWidget(
                QLabel("No saved tracks found — use Browse to locate a folder.")
            )

        browse_row = QHBoxLayout()
        browse_row.addStretch()
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.clicked.connect(self._on_browse)
        browse_row.addWidget(self._browse_btn)
        layout.addLayout(browse_row)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setEnabled(bool(self._dirs))
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select stems folder")
        if not folder:
            return
        path = Path(folder)
        if not _has_any_stem(path):
            QMessageBox.warning(
                self,
                "No stems found",
                "The selected folder contains no stem WAV files.\n"
                "Expected files like vocals.wav, drums.wav, etc.",
            )
            return
        self.selected_dir = path
        self._ok_btn.setEnabled(True)
        if self._combo is not None:
            for i in range(self._combo.count()):
                if self._combo.itemData(i) == path:
                    self._combo.setCurrentIndex(i)
                    return
            self._combo.insertItem(0, f"{path.name} (browsed)", userData=path)
            self._combo.setCurrentIndex(0)

    def _on_accept(self) -> None:
        if self.selected_dir is None and self._combo is not None:
            self.selected_dir = self._combo.currentData()
        self.accept()
