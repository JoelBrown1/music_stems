# Stem Splitter — Design Spec
**Date:** 2026-05-21
**Status:** Approved

## Overview

A macOS desktop app that separates audio tracks into up to 6 stems (vocals, drums, bass, guitar, piano, other) using Meta's Demucs model. Accepts three audio sources: YouTube URL, local file, or live system audio capture from Apple Music via BlackHole. Stems are saved as WAV files in a named subfolder under `~/Documents/music_tracks/`.

**Goals:**
- Practice/learning — isolate individual parts to play along with
- Remixing — produce clean stems for use in a DAW
- Transcription — analyse individual parts

**Non-goals:**
- Mobile or web versions
- Cloud processing or API-based separation
- Apple Music catalog browsing or streaming (local capture only)

---

## Architecture

Four clean layers. Core logic never touches the UI.

```
stem_splitter/
├── core/
│   ├── downloader.py     # yt-dlp wrapper — URL → local audio file
│   ├── recorder.py       # sounddevice wrapper — BlackHole capture → WAV
│   ├── separator.py      # Demucs wrapper — audio file → 6 stem WAVs
│   └── output.py         # Write stems to named subfolder, handle collisions
├── ui/
│   ├── main_window.py    # Single PyQt6 window, hosts all panels
│   ├── source_panel.py   # Tabbed: YouTube URL / Local File / Apple Music
│   ├── progress_panel.py # Download + separation progress bars
│   └── output_panel.py   # Stem file list + Open Folder button
└── main.py               # Entry point
```

Processing runs in a background `QThread` so the GUI stays responsive during download, conversion, and separation.

---

## UI Layout

Single window, three stacked sections.

### Source Panel (top)

Three tabs:

**YouTube URL tab:**
```
[ YouTube URL or paste link here          ]  [Start]
```

**Local File tab:**
```
[ File path                               ]  [Browse]  [Start]
```
File picker accepts MP3, WAV, FLAC, M4A.

**Apple Music tab:**
```
1. Play the track in Apple Music
2. Press Record when ready

Track name: [___________________________]

[● Record]   [■ Stop & Split]

⚠ Requires BlackHole virtual audio driver
  [Setup Guide]
```
If BlackHole is not detected at startup, the record controls are replaced by the setup guide only.

### Progress Panel (middle)

Two sequential progress bars:
- **Downloading** — yt-dlp progress (YouTube tab only; hidden for local file and Apple Music)
- **Separating** — Demucs progress, updates per-segment

On first run, a third bar appears for Demucs model weight download (~1 GB, cached to `~/.cache/torch/hub/` thereafter).

### Output Panel (bottom)

Appears after separation completes:
```
~/Documents/music_tracks/Song Title/
  vocals.wav   drums.wav   bass.wav
  guitar.wav   piano.wav   other.wav

                              [Open Folder]
```

---

## Processing Pipeline

Every source converges on a shared pipeline:

```
Source input
    │
    ▼
[Download / Record]   ← yt-dlp (YouTube) or sounddevice (Apple Music)
    │
    ▼
[Convert to WAV]      ← ffmpeg, 44.1 kHz / 16-bit
    │
    ▼
[Separate]            ← Demucs htdemucs_6s → 6 stem WAVs
    │
    ▼
[Write output]        ← ~/Documents/music_tracks/<Track Title>/
```

### Apple Music capture detail

- Records from the **BlackHole 2ch** virtual audio device
- Requires a one-time macOS Multi-Output Device setup (speakers + BlackHole) so the user hears playback while the app captures it
- The in-app setup guide covers BlackHole installation and Audio MIDI Setup configuration
- Track name is entered manually by the user; used as the output subfolder name
- Stop & Split immediately ends the recording and starts the Demucs pipeline — no confirmation step

---

## Error Handling

| Failure | Behaviour |
|---|---|
| Invalid YouTube URL | Inline error under URL field before pipeline starts |
| Age-restricted or private video | Error message with yt-dlp's reason |
| BlackHole not installed | Apple Music tab shows setup guide; record controls hidden |
| Demucs weights not cached | Auto-downloads on first run with dedicated progress bar |
| Demucs separation fails | Error shown with log snippet; output folder not created |
| Output folder already exists | Appends ` (2)`, ` (3)` etc. — never overwrites |

---

## Technology Stack

| Component | Library | Notes |
|---|---|---|
| Language | Python | 3.11+ |
| GUI | PyQt6 | 6.6+ |
| YouTube download | yt-dlp | latest |
| Audio conversion | ffmpeg | via subprocess |
| System audio capture | sounddevice | BlackHole 2ch as input device |
| Stem separation | demucs | htdemucs_6s model, 6 stems |
| Packaging | PyInstaller | macOS .app bundle |

---

## Output

Stems written to `~/Documents/music_tracks/<Track Title>/`:

```
vocals.wav
drums.wav
bass.wav
guitar.wav
piano.wav
other.wav
```

If a folder with that name already exists, the app appends ` (2)`, ` (3)`, etc.
