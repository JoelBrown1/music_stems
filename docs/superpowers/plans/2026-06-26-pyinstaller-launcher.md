# PyInstaller Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the stem-splitter app into a double-clickable `.app` (Mac) and `.exe` (Windows) using PyInstaller so friends can run it without any Python setup.

**Architecture:** Two independent pieces — a Python icon generator (`scripts/make_icon.py`) that draws a waveform icon and converts it to platform formats, and a PyInstaller spec file (`StemSplitter.spec`) driven by thin shell/batch build scripts. Zero changes to existing app code.

**Tech Stack:** PyInstaller, Pillow, macOS `iconutil` (Mac only), Python 3.11

## Global Constraints

- Python interpreter: `.venv/bin/python` (Mac/Linux), `.venv\Scripts\python.exe` (Windows)
- App entry point: `stem_splitter/main.py`
- App name: `StemSplitter`
- Bundle ID (Mac): `com.joelbrown.stemsplitter`
- Icon source: `resources/icon.png` (1024×1024 RGBA)
- Mac icon: `resources/icon.icns`
- Windows/Linux icon: `resources/icon.ico`
- Output (Mac): `dist/StemSplitter.app`
- Output (Windows): `dist/StemSplitter/StemSplitter.exe`
- Windowed mode — no terminal window pops up on launch
- `dist/` and `build/` must be excluded from git
- `upx=False` — UPX compression causes issues on Apple Silicon
- `Pillow` must be installed in `.venv` for icon generation

---

### Task 1: Icon generator (`scripts/make_icon.py`)

**Files:**
- Create: `scripts/make_icon.py`
- Create: `tests/test_make_icon.py`

**Interfaces:**
- Produces:
  - `generate_icon_png(path: Path, size: int = 1024) -> None` — draws dark waveform icon, saves as PNG to `path`, creates parent dirs as needed
  - `png_to_ico(png_path: Path, ico_path: Path) -> None` — converts PNG to multi-resolution `.ico`
  - `png_to_icns(png_path: Path, icns_path: Path) -> None` — converts PNG to `.icns` via macOS `iconutil`; raises `FileNotFoundError` if `iconutil` absent
  - CLI: `python scripts/make_icon.py` writes `resources/icon.png`, `resources/icon.ico`, and `resources/icon.icns` (Mac only)

- [ ] **Step 1: Install Pillow**

```bash
.venv/bin/pip install pillow
```
Expected: `Successfully installed pillow-...` or `Requirement already satisfied`

- [ ] **Step 2: Write failing tests**

Create `tests/test_make_icon.py`:

```python
# tests/test_make_icon.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from make_icon import generate_icon_png, png_to_ico


def test_generate_icon_png_creates_file(tmp_path):
    out = tmp_path / 'icon.png'
    generate_icon_png(out)
    assert out.exists()


def test_generate_icon_png_is_1024x1024(tmp_path):
    from PIL import Image
    out = tmp_path / 'icon.png'
    generate_icon_png(out)
    img = Image.open(str(out))
    assert img.size == (1024, 1024)


def test_generate_icon_png_is_rgba(tmp_path):
    from PIL import Image
    out = tmp_path / 'icon.png'
    generate_icon_png(out)
    img = Image.open(str(out))
    assert img.mode == 'RGBA'


def test_generate_icon_png_creates_parent_dirs(tmp_path):
    out = tmp_path / 'nested' / 'subdir' / 'icon.png'
    generate_icon_png(out)
    assert out.exists()


def test_png_to_ico_creates_file(tmp_path):
    png = tmp_path / 'icon.png'
    generate_icon_png(png)
    ico = tmp_path / 'icon.ico'
    png_to_ico(png, ico)
    assert ico.exists()


def test_png_to_ico_is_valid_ico(tmp_path):
    from PIL import Image
    png = tmp_path / 'icon.png'
    generate_icon_png(png)
    ico = tmp_path / 'icon.ico'
    png_to_ico(png, ico)
    img = Image.open(str(ico))
    assert img.format == 'ICO'
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_make_icon.py -v
```
Expected: `ImportError: No module named 'make_icon'`

- [ ] **Step 4: Create `scripts/make_icon.py`**

```python
#!/usr/bin/env python3
"""Generate app icons: resources/icon.png, icon.ico, icon.icns (Mac only)."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def generate_icon_png(path: Path, size: int = 1024) -> None:
    """Draw a dark 1024x1024 waveform icon and save as PNG."""
    img = Image.new('RGBA', (size, size), '#1a1a1a')
    draw = ImageDraw.Draw(img)

    purple = '#7c83f5'
    bar_count = 5
    bar_width = size // 10
    spacing = size // 15
    total_width = bar_count * bar_width + (bar_count - 1) * spacing
    x_start = (size - total_width) // 2
    heights = [0.3, 0.6, 0.9, 0.6, 0.3]

    for i, h in enumerate(heights):
        bar_h = int(size * h * 0.5)
        x = x_start + i * (bar_width + spacing)
        y = (size - bar_h) // 2
        draw.rectangle([x, y, x + bar_width, y + bar_h], fill=purple)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), 'PNG')
    print(f'  icon.png  → {path}')


def png_to_ico(png_path: Path, ico_path: Path) -> None:
    """Convert a PNG to a multi-resolution .ico file."""
    img = Image.open(str(png_path)).convert('RGBA')
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    resized = [img.resize(s, Image.LANCZOS) for s in sizes]
    resized[0].save(
        str(ico_path),
        format='ICO',
        sizes=[(s[0], s[1]) for s in sizes],
        append_images=resized[1:],
    )
    print(f'  icon.ico  → {ico_path}')


def png_to_icns(png_path: Path, icns_path: Path) -> None:
    """Convert PNG to .icns using macOS iconutil. Raises FileNotFoundError on non-Mac."""
    iconset = icns_path.with_suffix('.iconset')
    iconset.mkdir(exist_ok=True)
    img = Image.open(str(png_path)).convert('RGBA')
    sizes = {
        'icon_16x16.png': 16,     'icon_16x16@2x.png': 32,
        'icon_32x32.png': 32,     'icon_32x32@2x.png': 64,
        'icon_128x128.png': 128,  'icon_128x128@2x.png': 256,
        'icon_256x256.png': 256,  'icon_256x256@2x.png': 512,
        'icon_512x512.png': 512,  'icon_512x512@2x.png': 1024,
    }
    for name, size in sizes.items():
        img.resize((size, size), Image.LANCZOS).save(str(iconset / name))
    subprocess.run(
        ['iconutil', '-c', 'icns', str(iconset), '-o', str(icns_path)],
        check=True,
    )
    for f in iconset.iterdir():
        f.unlink()
    iconset.rmdir()
    print(f'  icon.icns → {icns_path}')


if __name__ == '__main__':
    root = Path(__file__).parent.parent
    resources = root / 'resources'
    png = resources / 'icon.png'

    print('Generating icons...')
    generate_icon_png(png)
    png_to_ico(png, resources / 'icon.ico')

    if sys.platform == 'darwin':
        try:
            png_to_icns(png, resources / 'icon.icns')
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f'  Warning: iconutil failed ({e}); .icns not generated')
    else:
        print('  Skipping .icns (not macOS)')
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_make_icon.py -v
```
Expected: 6 PASSED

- [ ] **Step 6: Run the script manually to verify output**

```bash
.venv/bin/python scripts/make_icon.py
```
Expected:
```
Generating icons...
  icon.png  → /Users/.../resources/icon.png
  icon.ico  → /Users/.../resources/icon.ico
  icon.icns → /Users/.../resources/icon.icns
```
Verify `resources/icon.png`, `resources/icon.ico`, and (on Mac) `resources/icon.icns` exist.

- [ ] **Step 7: Commit**

```bash
git add scripts/make_icon.py tests/test_make_icon.py resources/icon.png resources/icon.ico
# On Mac, also: git add resources/icon.icns
git commit -m "feat: add icon generator with purple waveform design"
```

---

### Task 2: PyInstaller spec + build scripts

**Files:**
- Create: `StemSplitter.spec`
- Create: `scripts/build.sh`
- Create: `scripts/build.bat`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `resources/icon.icns` (Mac), `resources/icon.ico` (Windows) — from Task 1
- Produces: `dist/StemSplitter.app` (Mac), `dist/StemSplitter/StemSplitter.exe` (Windows)

- [ ] **Step 1: Install PyInstaller**

```bash
.venv/bin/pip install pyinstaller
```
Expected: `Successfully installed pyinstaller-...` or `Requirement already satisfied`

- [ ] **Step 2: Add build artifacts to `.gitignore`**

Append to `.gitignore`:

```
# PyInstaller
dist/
build/
```

- [ ] **Step 3: Create `StemSplitter.spec`**

Create at project root:

```python
# StemSplitter.spec
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

icon = 'resources/icon.icns' if sys.platform == 'darwin' else 'resources/icon.ico'

datas = []
datas += collect_data_files('librosa')
datas += collect_data_files('basic_pitch')
datas += collect_data_files('madmom')
datas += collect_data_files('resampy')
datas += collect_data_files('demucs')

qt_datas, qt_binaries, qt_hidden = collect_all('PyQt6')
datas += qt_datas

hidden_imports = [
    'sounddevice',
    'soundfile',
    'resampy',
    'scipy.signal',
    'scipy.fft',
    'scipy.io',
    'scipy.io.wavfile',
    'madmom',
    'madmom.features',
    'madmom.features.beats',
    'madmom.features.onsets',
    'madmom.processors',
    'madmom.ml',
    'madmom.ml.rnn',
    'librosa',
    'librosa.core',
    'librosa.beat',
    'librosa.util',
    'librosa.filters',
    'demucs',
    'demucs.pretrained',
    'demucs.apply',
    'basic_pitch',
    'piano_transcription_inference',
    'pretty_midi',
    'sklearn',
    'sklearn.utils._cython_blas',
    'sklearn.neighbors._partition_nodes',
    'numpy',
    'numpy.core._methods',
    'numpy.lib.format',
    'yt_dlp',
]

a = Analysis(
    ['stem_splitter/main.py'],
    pathex=[],
    binaries=qt_binaries,
    datas=datas,
    hiddenimports=hidden_imports + qt_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StemSplitter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='StemSplitter',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='StemSplitter.app',
        icon='resources/icon.icns',
        bundle_identifier='com.joelbrown.stemsplitter',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.14.0',
        },
    )
```

- [ ] **Step 4: Create `scripts/build.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

PYTHON="$ROOT/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
    echo "ERROR: .venv not found. Run:"
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "==> Installing PyInstaller if needed..."
"$PYTHON" -c "import PyInstaller" 2>/dev/null \
    || "$PYTHON" -m pip install pyinstaller --quiet

echo "==> Installing Pillow if needed..."
"$PYTHON" -c "import PIL" 2>/dev/null \
    || "$PYTHON" -m pip install pillow --quiet

echo "==> Generating icons..."
"$PYTHON" scripts/make_icon.py

echo "==> Building app..."
"$PYTHON" -m PyInstaller StemSplitter.spec --noconfirm

echo ""
echo "Done! dist/StemSplitter.app is ready."
echo ""
echo "To share:"
echo "  cd dist && zip -r StemSplitter-mac.zip StemSplitter.app"
```

Make it executable:
```bash
chmod +x scripts/build.sh
```

- [ ] **Step 5: Create `scripts/build.bat`**

```bat
@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: .venv not found. Run:
    echo   python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo ==^> Installing PyInstaller if needed...
"%PYTHON%" -c "import PyInstaller" 2>nul || "%PYTHON%" -m pip install pyinstaller --quiet

echo ==^> Installing Pillow if needed...
"%PYTHON%" -c "import PIL" 2>nul || "%PYTHON%" -m pip install pillow --quiet

echo ==^> Generating icons...
"%PYTHON%" scripts\make_icon.py

echo ==^> Building app...
"%PYTHON%" -m PyInstaller StemSplitter.spec --noconfirm

echo.
echo Done! dist\StemSplitter\StemSplitter.exe is ready.
echo.
echo To share: zip the dist\StemSplitter\ folder
```

- [ ] **Step 6: Run the build**

```bash
./scripts/build.sh
```

Takes 2–5 minutes. Expected final lines:
```
Done! dist/StemSplitter.app is ready.
```

- [ ] **Step 7: Verify the app launches**

```bash
open dist/StemSplitter.app
```

The main window should appear with no terminal. If the app crashes silently, run it directly to see the error:

```bash
dist/StemSplitter.app/Contents/MacOS/StemSplitter
```

If you see `ModuleNotFoundError: No module named 'foo'`, add `'foo'` to `hidden_imports` in `StemSplitter.spec` and re-run `./scripts/build.sh`. Common ones to add:

- `'madmom.ml.rnn'`
- `'demucs.pretrained'`, `'demucs.states'`
- `'sklearn.utils._weight_vector'`
- `'scipy.special._ufuncs_cxx'`
- `'piano_transcription_inference.inference'`

Repeat until the app opens and the main features work (open a track, run the pipeline, open stems in the player).

**Note on first-run internet:** `demucs` downloads its pretrained separation models (~500MB) to `~/.cache/` the first time a track is processed — this is normal behavior and not a packaging bug. Friends need an internet connection the first time they split a track; subsequent runs use the cached models.

- [ ] **Step 8: Commit**

```bash
git add StemSplitter.spec scripts/build.sh scripts/build.bat .gitignore
git commit -m "feat: add PyInstaller spec and build scripts for distributable app"
```

- [ ] **Step 9: Share**

```bash
cd dist && zip -r StemSplitter-mac.zip StemSplitter.app
```

Send `StemSplitter-mac.zip` to friends via AirDrop, Google Drive, or iMessage. Recipients: unzip → right-click the `.app` → Open (first time only, to bypass Gatekeeper) → works forever after.
