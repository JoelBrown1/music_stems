# Load Pre-Saved Stems Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Open Stems…" entry point (menu bar + button) that loads a previously processed track into the Stem Player without re-running the pipeline.

**Architecture:** A new `LoadStemsDialog` handles folder discovery and selection. `MainWindow` receives the chosen `Path` and passes it directly to the existing `PlayerWindow(output_dir, parent)` — identical to what `_on_pipeline_finished` already does. No changes to `PlayerEngine` or `PlayerWindow`.

**Tech Stack:** PyQt6, pathlib, pytest, `STEMS` and `MUSIC_TRACKS_DIR` from `stem_splitter.core.output`

## Global Constraints

- PyQt6 only (no PyQt5, no PySide)
- All new UI files start with `from __future__ import annotations`
- Always use `STEMS` from `stem_splitter.core.output` — never hardcode stem names
- Default scan directory is `MUSIC_TRACKS_DIR` from `stem_splitter.core.output` (`~/Documents/music_tracks/`)
- Core never imports UI (four-layer architecture — `load_stems_dialog.py` lives in `stem_splitter/ui/`)
- Tests follow the existing pattern: test pure Python logic directly; do not instantiate Qt widgets in tests

---

### Task 1: Scan helpers with tests

**Files:**
- Create: `stem_splitter/ui/load_stems_dialog.py`
- Create: `tests/test_load_stems_dialog.py`

**Interfaces:**
- Produces:
  - `_has_any_stem(path: Path) -> bool` — True if `path` contains at least one `{stem}.wav` for stem in `STEMS`
  - `_find_stem_dirs(base: Path) -> list[Path]` — subdirs of `base` where `_has_any_stem` is True, sorted by `mtime` descending; returns `[]` if `base` does not exist

- [ ] **Step 1: Write failing tests**

```python
# tests/test_load_stems_dialog.py
import time
from pathlib import Path
from stem_splitter.ui.load_stems_dialog import _has_any_stem, _find_stem_dirs
from stem_splitter.core.output import STEMS


def test_has_any_stem_true_when_one_stem_present(tmp_path):
    (tmp_path / f"{STEMS[0]}.wav").write_bytes(b"")
    assert _has_any_stem(tmp_path) is True


def test_has_any_stem_false_when_no_stems(tmp_path):
    (tmp_path / "random.txt").write_text("")
    assert _has_any_stem(tmp_path) is False


def test_has_any_stem_true_for_partial_stems(tmp_path):
    (tmp_path / "vocals.wav").write_bytes(b"")
    # only one of six stems — still True
    assert _has_any_stem(tmp_path) is True


def test_find_stem_dirs_empty_base(tmp_path):
    assert _find_stem_dirs(tmp_path) == []


def test_find_stem_dirs_nonexistent_base():
    assert _find_stem_dirs(Path("/tmp/does_not_exist_xyz_graphify")) == []


def test_find_stem_dirs_excludes_no_stem_dirs(tmp_path):
    d = tmp_path / "no_stems"
    d.mkdir()
    (d / "random.txt").write_text("")
    assert _find_stem_dirs(tmp_path) == []


def test_find_stem_dirs_excludes_files_at_base(tmp_path):
    (tmp_path / "vocals.wav").write_bytes(b"")  # file, not subdir
    assert _find_stem_dirs(tmp_path) == []


def test_find_stem_dirs_includes_partial_stem_dir(tmp_path):
    d = tmp_path / "partial"
    d.mkdir()
    (d / "vocals.wav").write_bytes(b"")
    assert _find_stem_dirs(tmp_path) == [d]


def test_find_stem_dirs_sorted_newest_first(tmp_path):
    old = tmp_path / "old_track"
    old.mkdir()
    (old / "vocals.wav").write_bytes(b"")
    time.sleep(0.05)
    new = tmp_path / "new_track"
    new.mkdir()
    (new / "drums.wav").write_bytes(b"")
    result = _find_stem_dirs(tmp_path)
    assert result == [new, old]


def test_find_stem_dirs_multiple_tracks(tmp_path):
    for name in ("alpha", "beta", "gamma"):
        d = tmp_path / name
        d.mkdir()
        (d / "bass.wav").write_bytes(b"")
    result = _find_stem_dirs(tmp_path)
    assert len(result) == 3
    assert all(isinstance(p, Path) for p in result)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_load_stems_dialog.py -v
```
Expected: `ModuleNotFoundError: No module named 'stem_splitter.ui.load_stems_dialog'`

- [ ] **Step 3: Create `load_stems_dialog.py` with the two helpers**

```python
# stem_splitter/ui/load_stems_dialog.py
from __future__ import annotations

from pathlib import Path
from stem_splitter.core.output import STEMS, MUSIC_TRACKS_DIR


def _has_any_stem(path: Path) -> bool:
    return any((path / f"{stem}.wav").exists() for stem in STEMS)


def _find_stem_dirs(base: Path) -> list[Path]:
    if not base.exists():
        return []
    dirs = [d for d in base.iterdir() if d.is_dir() and _has_any_stem(d)]
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_load_stems_dialog.py -v
```
Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/ui/load_stems_dialog.py tests/test_load_stems_dialog.py
git commit -m "feat: add _find_stem_dirs and _has_any_stem helpers with tests"
```

---

### Task 2: `LoadStemsDialog` class

**Files:**
- Modify: `stem_splitter/ui/load_stems_dialog.py` (append `LoadStemsDialog` class)

**Interfaces:**
- Consumes: `_has_any_stem(path: Path) -> bool` and `_find_stem_dirs(base: Path) -> list[Path]` from Task 1; `MUSIC_TRACKS_DIR` from `stem_splitter.core.output`
- Produces: `LoadStemsDialog(parent=None)` — a `QDialog` with `.selected_dir: Path | None` (None if user cancelled or no selection made)

- [ ] **Step 1: Append `LoadStemsDialog` to `load_stems_dialog.py`**

Add these imports at the top of the file (after the existing imports):

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QDialogButtonBox, QFileDialog, QMessageBox,
)
```

Then append the class at the bottom of the file:

```python
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
```

- [ ] **Step 2: Run existing tests to confirm nothing broke**

```bash
python -m pytest tests/test_load_stems_dialog.py -v
```
Expected: all 10 tests still PASS (helpers are unchanged)

- [ ] **Step 3: Manually smoke-test the dialog in isolation**

```bash
python -c "
import sys
from PyQt6.QtWidgets import QApplication
from stem_splitter.ui.load_stems_dialog import LoadStemsDialog
app = QApplication(sys.argv)
dlg = LoadStemsDialog()
if dlg.exec():
    print('Selected:', dlg.selected_dir)
else:
    print('Cancelled')
"
```

Verify:
1. Dialog opens with a dropdown listing tracks from `~/Documents/music_tracks/` (or the empty-state label if none exist)
2. Browse… opens a folder picker; picking a folder with no stems shows the warning and returns to the dialog
3. Browse… picking a valid stems folder enables OK
4. OK returns the selected path; Cancel returns None

- [ ] **Step 4: Commit**

```bash
git add stem_splitter/ui/load_stems_dialog.py
git commit -m "feat: implement LoadStemsDialog with dropdown and browse fallback"
```

---

### Task 3: `MainWindow` integration

**Files:**
- Modify: `stem_splitter/ui/main_window.py`

**Interfaces:**
- Consumes: `LoadStemsDialog(parent)` from Task 2 (`.selected_dir: Path | None`); existing `PlayerWindow(output_dir: Path, parent)` from `stem_splitter.ui.player_window`

- [ ] **Step 1: Add import**

In `stem_splitter/ui/main_window.py`, add to the existing UI import block:

```python
from stem_splitter.ui.load_stems_dialog import LoadStemsDialog
```

Also add `QPushButton` to the existing `QWidgets` import (it is not currently imported):

```python
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QMessageBox, QPushButton
```

- [ ] **Step 2: Add `_open_load_stems_dialog` method**

Add this method to `MainWindow`:

```python
def _open_load_stems_dialog(self) -> None:
    dlg = LoadStemsDialog(parent=self)
    if dlg.exec() and dlg.selected_dir:
        if self._player is not None:
            self._player.close()
        self._player = PlayerWindow(dlg.selected_dir, parent=self)
        self._player.show()
```

- [ ] **Step 3: Add `File` menu bar**

In `MainWindow.__init__`, after `self._source.start_pipeline.connect(...)` and before the end of `__init__`, add:

```python
menu_bar = self.menuBar()
file_menu = menu_bar.addMenu("File")
open_stems_action = file_menu.addAction("Open Stems…")
open_stems_action.setShortcut("Ctrl+O")
open_stems_action.triggered.connect(self._open_load_stems_dialog)
```

- [ ] **Step 4: Add `Open Stems…` button to main layout**

In `MainWindow.__init__`, after `layout.addWidget(self._output)`, add:

```python
open_btn = QPushButton("Open Stems…")
open_btn.clicked.connect(self._open_load_stems_dialog)
layout.addWidget(open_btn)
```

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
python -m pytest tests/ -v
```
Expected: all existing tests PASS plus the 10 new load_stems tests

- [ ] **Step 6: Manually test the full integration**

```bash
python -m stem_splitter.main
```

Verify:
1. A `File` menu appears in the menu bar with `Open Stems…` (Ctrl+O / ⌘O on Mac)
2. An `Open Stems…` button appears at the bottom of the main window
3. Both the menu item and the button open `LoadStemsDialog`
4. Selecting a track and clicking OK opens `PlayerWindow` for that track
5. Stems present in the folder are active; missing stems are greyed out
6. Opening a second track closes the first player before opening the new one
7. The pipeline still works end-to-end (run a track through to confirm `_on_pipeline_finished` is unaffected)

- [ ] **Step 7: Commit**

```bash
git add stem_splitter/ui/main_window.py
git commit -m "feat: add Open Stems menu and button to MainWindow"
```
