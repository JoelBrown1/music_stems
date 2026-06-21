# Load Pre-Saved Stems Design

**Date:** 2026-06-21  
**Status:** Approved

## Summary

Allow the user to open the Stem Player for a previously processed track without re-running the pipeline. Two entry points (menu bar + button) open a `LoadStemsDialog` that lets the user pick a saved output folder from a dropdown list or via a Browse picker. The selected folder is passed directly to `PlayerWindow`, with no changes to `PlayerEngine` or `PlayerWindow`.

## Architecture

Follows the existing four-layer architecture (core never imports UI). No new core logic needed — the player already handles partially-populated stem directories by greying out missing stems.

**New file:** `stem_splitter/ui/load_stems_dialog.py`  
**Modified file:** `stem_splitter/ui/main_window.py`

## Components

### `LoadStemsDialog` (`stem_splitter/ui/load_stems_dialog.py`)

A `QDialog` with:
- A `QComboBox` populated by `_find_stem_dirs()`, sorted newest-first by `mtime`
- A **Browse…** `QPushButton` that opens `QFileDialog.getExistingDirectory`
- **OK** / **Cancel** buttons; OK is disabled until a valid folder is selected
- A `.selected_dir: Path | None` property — `None` if cancelled

Module-level helper:
```python
def _find_stem_dirs(base: Path) -> list[Path]:
    # Returns subdirs of base that contain at least one {stem}.wav,
    # sorted by mtime descending.
```

**Empty state:** if `_find_stem_dirs` returns an empty list, the combo is hidden and a label reads "No saved tracks found — use Browse to locate a folder."

### `MainWindow` changes (`stem_splitter/ui/main_window.py`)

- **Menu bar**: add a `File` menu with `Open Stems…` (shortcut ⌘O)
- **Button**: add an `Open Stems…` `QPushButton` at the bottom of the main layout
- Both call `_open_load_stems_dialog()`

```python
def _open_load_stems_dialog(self) -> None:
    dlg = LoadStemsDialog(parent=self)
    if dlg.exec() and dlg.selected_dir:
        if self._player is not None:
            self._player.close()
        self._player = PlayerWindow(dlg.selected_dir, parent=self)
        self._player.show()
```

## Data Flow

```
User clicks "Open Stems…" (button or menu)
  → _open_load_stems_dialog()
    → LoadStemsDialog.exec()
      → _find_stem_dirs(~/Documents/music_tracks/) → QComboBox
      → OR: QFileDialog.getExistingDirectory() → Browse path
    → returns selected Path
  → PlayerWindow(output_dir, parent=self).show()
```

## Validation

- **Scan**: any directory with at least one `{stem}.wav` present is accepted
- **Browse**: same check applied; if zero stem wavs found, `QMessageBox.warning` and dialog stays open
- **Partial stems**: accepted — missing stems render greyed-out in the player (existing behaviour)

## Error Handling

| Scenario | Behaviour |
|---|---|
| No saved tracks in default dir | Combo hidden, label shown, OK disabled |
| Browse picks folder with no stems | Warning dialog, picker stays open |
| Browse picks partial folder | Accepted, missing stems greyed in player |
| Player already open | Existing player closed before new one opens |

## Out of Scope

- Populating the output panel (MIDI conversion) for loaded tracks
- Persisting recently-opened paths across sessions
- Preview / auditioning stems before loading
