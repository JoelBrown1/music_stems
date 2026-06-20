# Stem Splitter

A macOS desktop app that separates any song into individual stems (vocals, drums, bass, guitar, piano, other) and converts each one to MIDI.

## Requirements

- macOS (required for the Apple Music capture feature)
- Python 3.11 or later
- [BlackHole 2ch](https://existential.audio/blackhole/) — virtual audio driver, needed only for Apple Music recording

## Installation

### 1. Clone the repo

```bash
git clone git@github.com:JoelBrown1/music_stems.git
cd music_stems
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The first run of Demucs will download the `htdemucs_6s` model (~1 GB) automatically.

### 3. Install BlackHole (Apple Music capture only)

Download and install [BlackHole 2ch](https://existential.audio/blackhole/).

Then open **Audio MIDI Setup** (Applications → Utilities) and create a **Multi-Output Device** that includes both BlackHole 2ch and your speakers. Set this Multi-Output Device as your system output so audio routes to both simultaneously. The app detects BlackHole automatically — if it isn't found, the Apple Music tab shows a setup prompt instead.

## Running the app

```bash
source .venv/bin/activate   # if not already active
python -m stem_splitter.main
```

## How it works

The app has three ways to get audio in:

**YouTube URL** — paste a YouTube link and click Start. The app downloads the audio via yt-dlp.

**Local File** — browse to any `.mp3`, `.wav`, `.flac`, or `.m4a` file on your machine.

**Apple Music** — play a track in Apple Music, then hit Record in the app. Stop recording when done. Requires BlackHole.

Once audio is loaded, Demucs splits it into six stems. Each stem can then be converted to MIDI. Click the gear icon (⚙) next to any stem to tune the MIDI conversion parameters before converting.

## MIDI engines

Each stem uses a different engine under the hood:

| Stem | Engine |
|------|--------|
| Drums | madmom RNN onset detector → GM MIDI mapping |
| Piano | piano_transcription_inference |
| Vocals, bass, guitar, other | Basic Pitch |

## Running tests

```bash
source .venv/bin/activate
pytest
```
