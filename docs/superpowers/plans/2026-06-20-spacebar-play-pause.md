# Spacebar Play/Pause Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user press Space to toggle play/pause in the Stem Player window.

**Architecture:** Override `keyPressEvent` in `PlayerWindow` and set `StrongFocus` so the window can receive keyboard events. No new files, no new dependencies.

**Tech Stack:** PyQt6 (`Qt.FocusPolicy`, `Qt.Key`, `QDialog.keyPressEvent`)

---

## File Map

| Action | Path | Change |
|--------|------|--------|
| Modify | `stem_splitter/ui/player_window.py` | Add focus policy + `keyPressEvent` to `PlayerWindow` |

---

## Task 1: Spacebar toggles play/pause in PlayerWindow

**Files:**
- Modify: `stem_splitter/ui/player_window.py`

No unit tests — Qt event dispatch requires a running `QApplication` and is verified manually per the spec.

- [ ] **Step 1: Add focus policy to `PlayerWindow.__init__`**

In `stem_splitter/ui/player_window.py`, find the end of `PlayerWindow.__init__`. It currently ends with:

```python
        if parent is not None:
            self.move(parent.geometry().right() + 8, parent.geometry().top())
```

Add two lines directly after that block:

```python
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
```

`StrongFocus` lets the dialog receive keyboard events via mouse click or tab. `setFocus()` gives the window focus immediately on open — spacebar works without the user having to click first.

- [ ] **Step 2: Add `keyPressEvent` to `PlayerWindow`**

Add this method to `PlayerWindow` (anywhere after `closeEvent` is a good place — at the end of the class):

```python
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._on_play_pause()
        else:
            super().keyPressEvent(event)
```

`Qt.Key.Key_Space` is already available — `Qt` is imported from `PyQt6.QtCore` at the top of the file. Non-spacebar keys are forwarded to `super()` so Escape (close dialog), Tab (focus cycling), and other Qt defaults keep working.

- [ ] **Step 3: Verify the file imports cleanly**

```bash
python -c "from stem_splitter.ui.player_window import PlayerWindow; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Manually verify the behaviour**

Run the app:

```bash
.venv/bin/python -m stem_splitter.main
```

Load any audio file and wait for the Stem Player window to open. Then:

1. Press Space — audio should start playing
2. Press Space again — audio should pause
3. Click the volume slider for any stem, then press Space — nothing happens (slider has focus)
4. Click anywhere on the player window background, then press Space — audio toggles again

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/ui/player_window.py
git commit -m "feat: spacebar toggles play/pause in PlayerWindow"
```
