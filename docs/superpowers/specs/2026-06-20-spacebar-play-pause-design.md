# Spacebar Play/Pause Design

**Date:** 2026-06-20
**Status:** Approved

## Overview

Add spacebar keyboard shortcut to `PlayerWindow` to toggle play/pause, matching standard media player behaviour.

## Change

**File:** `stem_splitter/ui/player_window.py` — `PlayerWindow` only.

### Focus policy

In `PlayerWindow.__init__`, after the QTimer is started:

```python
self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
self.setFocus()
```

`StrongFocus` allows the window to receive keyboard focus via mouse click or tab. `setFocus()` ensures the window has focus immediately on open so spacebar works without the user clicking first.

### Key handler

```python
def keyPressEvent(self, event):
    if event.key() == Qt.Key.Key_Space:
        self._on_play_pause()
    else:
        super().keyPressEvent(event)
```

All non-spacebar keys are passed to `super()` to preserve default Qt behaviour (tab navigation, dialog close on Escape, etc.).

## Focus behaviour

Child widgets (QPushButton, QSlider) steal keyboard focus when clicked. After interacting with a control, the user clicks anywhere on the player window background to return focus to the window, then spacebar works again. This is standard Qt dialog behaviour and requires no additional handling.

## Error handling

None required. `_on_play_pause()` already handles the no-audio-device case with a `QMessageBox.warning`.

## Testing

No unit tests — Qt event handling is verified manually:
1. Open player window → press Space → audio plays
2. Press Space again → audio pauses
3. Click a button → press Space → confirm spacebar still toggles (after clicking window background to restore focus)
