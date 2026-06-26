# Stem Splitter

A macOS desktop app that separates any song into individual stems (vocals, drums, bass, guitar, piano, other) and converts each one to MIDI.

---

## Setup Guide

This guide walks you through everything from scratch. Each step includes the exact commands to copy and paste — you don't need to know how to code.

**What you'll need:**
- A Mac running macOS 10.14 or later
- An internet connection (the setup downloads about 2 GB of files total)
- About 30 minutes

---

### Step 1 — Open Terminal

Terminal is a text-based way to talk to your Mac. Every command in this guide gets typed (or pasted) there and run by pressing **Enter**.

To open it: press **Command + Space**, type `Terminal`, and press Enter.

---

### Step 2 — Install Homebrew

Homebrew is a tool that makes it easy to install software on a Mac. If you already have it, skip this step.

Paste this into Terminal and press Enter:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

It will ask for your Mac login password. Type it (nothing appears on screen while you type — that's normal) and press Enter. Follow any prompts. This takes a few minutes.

When it's done, if it tells you to run commands to add Homebrew to your PATH, run those now (it prints them at the end with instructions). Then close Terminal and reopen it.

---

### Step 3 — Install Python 3.11

The app requires Python version 3.11. Your Mac may already have Python, but it's likely an older version that won't work.

```bash
brew install python@3.11
```

When it finishes, verify it worked:

```bash
python3.11 --version
```

You should see something like `Python 3.11.15`. If you do, you're good.

---

### Step 4 — Install Git

Git is how you download the app's code. It may already be installed.

```bash
brew install git
```

---

### Step 5 — Download the App

This downloads all the code to your computer. Run these two commands one at a time:

```bash
git clone https://github.com/JoelBrown1/music_stems.git
```

```bash
cd music_stems
```

The first command downloads the code into a folder called `music_stems`. The second command moves you into that folder.

---

### Step 6 — Create a Virtual Environment

A virtual environment is like a clean, isolated box for the app's software to live in — it won't interfere with anything else on your Mac.

```bash
python3.11 -m venv .venv
```

This creates the box. You only need to do this once.

---

### Step 7 — Install the App's Dependencies

The app needs a collection of tools (called dependencies) to work — things like AI models for separating audio and tools for MIDI conversion.

Run this command:

```bash
.venv/bin/pip install -r requirements.txt
```

**This will take 10–20 minutes** and download roughly 1–2 GB of files. That's normal. You'll see a lot of text scrolling by — as long as it doesn't say `ERROR`, it's working.

---

### Step 8 — Run the App

Every time you want to open the app, run this from the `music_stems` folder:

```bash
.venv/bin/python -m stem_splitter.main
```

A window will appear. That's the app.

> **Tip:** If you open a new Terminal window and the app won't start, you might be in the wrong folder. Run `cd ~/music_stems` first to get back to the right place.

---

### First Time You Use It

The very first time you split a song, the app will download the AI model it uses (called `htdemucs_6s`, about 1 GB). This happens automatically in the background and only happens once. You'll see a progress bar.

---

## How to Use the App

There are three ways to load a song:

**YouTube URL** — Paste a YouTube link into the box and click Start. The app downloads the audio.

**Local File** — Click Browse and pick a `.mp3`, `.wav`, `.flac`, or `.m4a` file from your computer.

**Apple Music** — Play a song in Apple Music and hit Record in the app. Requires extra setup (see below).

Once the song is loaded, the app splits it into six separate tracks: vocals, drums, bass, guitar, piano, and everything else. Click the play button on any stem to hear it. Click the **MIDI** button to convert a stem to a MIDI file.

---

## Apple Music Recording (Optional)

This lets you record whatever's playing in Apple Music. It requires a free virtual audio driver called BlackHole.

### Install BlackHole

Download and install [BlackHole 2ch](https://existential.audio/blackhole/). It's free.

### Set Up Audio Routing

After installing BlackHole:

1. Open **Audio MIDI Setup** — press Command + Space, type `Audio MIDI Setup`, press Enter
2. Click the **+** button in the bottom-left corner and choose **Create Multi-Output Device**
3. Check the boxes for both **BlackHole 2ch** and your speakers (or headphones)
4. Right-click the new Multi-Output Device and choose **Use This Device For Sound Output**

Now audio plays through your speakers AND gets captured by the app at the same time.

To stop using this setup, go back to Audio MIDI Setup and switch your output back to your normal speakers.

---

## Troubleshooting

**"command not found: brew"**
Homebrew didn't install correctly, or Terminal needs to be restarted. Close Terminal, reopen it, and try the Homebrew install command again.

**"python3.11: command not found"**
Try closing Terminal and reopening it. If it still doesn't work, Homebrew may need you to add it to your PATH — look at the output from the Homebrew install step for instructions.

**"No module named 'stem_splitter'"**
You're in the wrong folder. Run `cd ~/music_stems` and try again.

**The app window opens but is blank or crashes immediately**
This can happen if a dependency didn't install correctly. Try running:
```bash
.venv/bin/pip install -r requirements.txt
```
again. It's safe to run multiple times.

**Splitting takes a really long time**
That's normal for the first split — the AI model is doing a lot of work. On an Apple Silicon Mac (M1/M2/M3), a 3-minute song typically takes 1–2 minutes. On an older Intel Mac it may take 5–10 minutes.
