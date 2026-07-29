# YouTube Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user type a search term into the existing YouTube tab's field (instead of only accepting an exact URL), see a results list with thumbnails, and pick one to start the pipeline exactly as pasting its URL would.

**Architecture:** `search_youtube()` shells out to the already-bundled `yt-dlp` binary (`ytsearchN:<query> --dump-json --flat-playlist --skip-download`) and parses one JSON object per line into `SearchResult`. A new `SearchWorker(QThread)` runs it off the UI thread, mirroring the existing `PipelineWorker`/`MidiWorker` pattern. `SourcePanel`'s YouTube tab branches on `is_valid_youtube_url()`: valid URL keeps today's behavior unchanged; otherwise it launches `SearchWorker`, shows results in a `QListWidget`, and loads thumbnails asynchronously via `QNetworkAccessManager`. Activating a result builds the same `(url, track_name, True)` tuple the URL path already emits via `start_pipeline` — nothing downstream of that signal changes.

**Tech Stack:** PyQt6 (`QtWidgets`, `QtCore`, `QtGui`, `QtNetwork` — all part of the existing PyQt6 dependency, no new packages), the `yt-dlp` binary already bundled for downloads, pytest.

## Global Constraints

- No new dependencies — search uses the already-bundled `yt-dlp` binary and PyQt6's built-in `QtNetwork` module.
- `max_results` fixed at 5 — not user-configurable in this iteration.
- Search/zero-results/thumbnail errors use the existing inline red-label pattern (`_url_error`) — no popup dialogs.
- Track names from search results go through `_sanitize_track_name()` before being used as an output directory name (video titles can contain `/`, unlike URL-derived video IDs).
- Core (`stem_splitter/core/`) never imports UI — four-layer architecture is unchanged.
- Tests follow the existing project pattern: test pure Python logic directly; do not instantiate live `QWidget`/`QListWidget` interaction in automated tests (this codebase has no `pytest-qt` and no such tests exist — UI wiring is verified by manual smoke test instead, same as `LoadStemsDialog`'s plan).
- `QThread`-based workers are tested by calling `.run()` directly (not `.start()`), using the existing module-scoped `qapp` fixture in `tests/test_worker.py`.

---

### Task 1: `SearchResult` + `search_youtube()` in `downloader.py`

**Files:**
- Modify: `stem_splitter/core/downloader.py`
- Modify: `tests/test_downloader.py`

**Interfaces:**
- Produces:
  - `SearchResult` dataclass: `video_id: str, title: str, channel: str, duration_seconds: int, thumbnail_url: str, url: str`
  - `search_youtube(query: str, max_results: int = 5) -> list[SearchResult]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_downloader.py` (add `SearchResult, search_youtube` to the existing import line):

```python
from stem_splitter.core.downloader import (
    is_valid_youtube_url, download_audio, SearchResult, search_youtube,
)

_SEARCH_STDOUT = (
    '{"id": "abc123", "title": "Song One", "channel": "Artist A", '
    '"duration": 215.0, "thumbnails": [{"url": "https://i.ytimg.com/vi/abc123/default.jpg"}, '
    '{"url": "https://i.ytimg.com/vi/abc123/hq720.jpg"}], '
    '"url": "https://www.youtube.com/watch?v=abc123"}\n'
    '{"id": "def456", "title": "Song Two", "channel": "Artist B", '
    '"duration": 180.0, "thumbnails": [{"url": "https://i.ytimg.com/vi/def456/default.jpg"}], '
    '"url": "https://www.youtube.com/watch?v=def456"}\n'
)

def test_search_youtube_calls_yt_dlp_with_correct_args():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        search_youtube("some query", max_results=5)
    args = mock_run.call_args[0][0]
    assert args[0].endswith("yt-dlp")
    assert args[1] == "ytsearch5:some query"
    assert "--dump-json" in args
    assert "--flat-playlist" in args
    assert "--skip-download" in args

def test_search_youtube_parses_results():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=_SEARCH_STDOUT, stderr="")
        results = search_youtube("some query")
    assert results == [
        SearchResult(
            video_id="abc123", title="Song One", channel="Artist A",
            duration_seconds=215, thumbnail_url="https://i.ytimg.com/vi/abc123/hq720.jpg",
            url="https://www.youtube.com/watch?v=abc123",
        ),
        SearchResult(
            video_id="def456", title="Song Two", channel="Artist B",
            duration_seconds=180, thumbnail_url="https://i.ytimg.com/vi/def456/default.jpg",
            url="https://www.youtube.com/watch?v=def456",
        ),
    ]

def test_search_youtube_returns_empty_list_for_no_results():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert search_youtube("nonsense query") == []

def test_search_youtube_raises_on_yt_dlp_failure():
    with patch("stem_splitter.core.downloader.subprocess.run") as mock_run:
        mock_run.side_effect = CalledProcessError(1, "yt-dlp", stderr="Network error")
        with pytest.raises(CalledProcessError):
            search_youtube("some query")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_downloader.py -v
```
Expected: `ImportError: cannot import name 'SearchResult'` (or `'search_youtube'`)

- [ ] **Step 3: Implement `SearchResult` and `search_youtube()`**

In `stem_splitter/core/downloader.py`, add imports at the top:

```python
import json
from dataclasses import dataclass
```

Append to the end of the file:

```python
@dataclass
class SearchResult:
    video_id: str
    title: str
    channel: str
    duration_seconds: int
    thumbnail_url: str
    url: str

def search_youtube(query: str, max_results: int = 5) -> list[SearchResult]:
    result = subprocess.run(
        [_YT_DLP, f"ytsearch{max_results}:{query}",
         "--dump-json", "--flat-playlist", "--skip-download"],
        capture_output=True, text=True, check=True,
    )
    results = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        entry = json.loads(line)
        thumbnails = entry.get("thumbnails") or []
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else ""
        video_id = entry["id"]
        results.append(SearchResult(
            video_id=video_id,
            title=entry.get("title", ""),
            channel=entry.get("channel") or entry.get("uploader") or "",
            duration_seconds=int(entry.get("duration") or 0),
            thumbnail_url=thumbnail_url,
            url=entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        ))
    return results
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_downloader.py -v
```
Expected: all tests PASS (existing + 4 new)

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/downloader.py tests/test_downloader.py
git commit -m "feat: add search_youtube() and SearchResult to downloader"
```

---

### Task 2: `SearchWorker` in `worker.py`

**Files:**
- Modify: `stem_splitter/core/worker.py`
- Modify: `tests/test_worker.py`

**Interfaces:**
- Consumes: `search_youtube(query: str, max_results: int = 5) -> list[SearchResult]` and `SearchResult` from Task 1
- Produces: `SearchWorker(query: str)` — a `QThread` with `finished = pyqtSignal(list)` (emits `list[SearchResult]`) and `error = pyqtSignal(str)`

- [ ] **Step 1: Write the failing tests**

In `tests/test_worker.py`, extend the existing import lines:

```python
from stem_splitter.core.worker import PipelineWorker, MidiWorker, SearchWorker
from stem_splitter.core.downloader import SearchResult
```

Append:

```python
def test_search_worker_emits_finished_with_results(qapp):
    fake_results = [SearchResult(
        video_id="abc123", title="Song One", channel="Artist A",
        duration_seconds=215, thumbnail_url="https://i.ytimg.com/vi/abc123/hq720.jpg",
        url="https://www.youtube.com/watch?v=abc123",
    )]
    finished = []
    with patch("stem_splitter.core.worker.search_youtube", return_value=fake_results):
        worker = SearchWorker("some query")
        worker.finished.connect(lambda r: finished.append(r))
        worker.run()
    assert finished == [fake_results]


def test_search_worker_emits_error_on_failure(qapp):
    errors = []
    with patch("stem_splitter.core.worker.search_youtube", side_effect=RuntimeError("boom")):
        worker = SearchWorker("some query")
        worker.error.connect(lambda msg: errors.append(msg))
        worker.run()
    assert errors == ["boom"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_worker.py -v
```
Expected: `ImportError: cannot import name 'SearchWorker'`

- [ ] **Step 3: Implement `SearchWorker`**

In `stem_splitter/core/worker.py`, change the existing downloader import line:

```python
from stem_splitter.core.downloader import download_audio, search_youtube
```

Append the class at the end of the file:

```python
class SearchWorker(QThread):
    finished = pyqtSignal(list)   # list[SearchResult]
    error = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            self.finished.emit(search_youtube(self.query))
        except Exception as e:
            self.error.emit(str(e))
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_worker.py -v
```
Expected: all tests PASS (existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/core/worker.py tests/test_worker.py
git commit -m "feat: add SearchWorker for background YouTube search"
```

---

### Task 3: Pure helpers `_sanitize_track_name()` and `_build_pipeline_args()`

**Files:**
- Modify: `stem_splitter/ui/source_panel.py`
- Create: `tests/test_source_panel.py`

**Interfaces:**
- Consumes: `SearchResult` from Task 1
- Produces:
  - `_sanitize_track_name(title: str) -> str`
  - `_build_pipeline_args(result: SearchResult) -> tuple[str, str, bool]` — returns `(result.url, _sanitize_track_name(result.title), True)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_source_panel.py`:

```python
from stem_splitter.ui.source_panel import _sanitize_track_name, _build_pipeline_args
from stem_splitter.core.downloader import SearchResult


def test_sanitize_track_name_replaces_slash():
    assert _sanitize_track_name("AC/DC - Back In Black") == "AC_DC - Back In Black"


def test_sanitize_track_name_replaces_multiple_unsafe_chars():
    assert _sanitize_track_name("Weird: Title?") == "Weird_ Title_"


def test_sanitize_track_name_strips_surrounding_whitespace():
    assert _sanitize_track_name("  Padded Title  ") == "Padded Title"


def test_build_pipeline_args_returns_expected_tuple():
    result = SearchResult(
        video_id="abc123", title="AC/DC - Back In Black",
        channel="Sony Music", duration_seconds=255,
        thumbnail_url="https://i.ytimg.com/vi/abc123/hq720.jpg",
        url="https://www.youtube.com/watch?v=abc123",
    )
    assert _build_pipeline_args(result) == (
        "https://www.youtube.com/watch?v=abc123", "AC_DC - Back In Black", True,
    )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_source_panel.py -v
```
Expected: `ImportError: cannot import name '_sanitize_track_name'`

- [ ] **Step 3: Implement the helpers**

In `stem_splitter/ui/source_panel.py`, add near the top of the file (after the existing imports, before the `SourcePanel` class):

```python
import re
from stem_splitter.core.downloader import is_valid_youtube_url, SearchResult


def _sanitize_track_name(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", title).strip()


def _build_pipeline_args(result: SearchResult) -> tuple[str, str, bool]:
    return (result.url, _sanitize_track_name(result.title), True)
```

(This replaces the existing `from stem_splitter.core.downloader import is_valid_youtube_url` line — `SearchResult` is now imported alongside it.)

- [ ] **Step 4: Run tests to confirm they pass**

```bash
.venv/bin/python -m pytest tests/test_source_panel.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/ui/source_panel.py tests/test_source_panel.py
git commit -m "feat: add _sanitize_track_name and _build_pipeline_args helpers"
```

---

### Task 4: Wire the results list into `SourcePanel`

**Files:**
- Modify: `stem_splitter/ui/source_panel.py`

**Interfaces:**
- Consumes: `SearchWorker(query: str)` from Task 2; `_build_pipeline_args(result) -> tuple[str, str, bool]` from Task 3; existing `is_valid_youtube_url`, `start_pipeline` signal
- Produces: `SourcePanel` now shows a results list and starts the pipeline when a result is activated, in addition to its existing URL-paste behavior

- [ ] **Step 1: Add required imports**

In `stem_splitter/ui/source_panel.py`, update the `QtWidgets` import to include `QListWidget` and `QListWidgetItem`:

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLineEdit, QPushButton, QLabel, QFileDialog,
    QListWidget, QListWidgetItem,
)
```

Update the `QtCore` import to include `Qt`:

```python
from PyQt6.QtCore import pyqtSignal, Qt
```

Add the worker import:

```python
from stem_splitter.core.worker import SearchWorker
```

- [ ] **Step 2: Replace `_make_youtube_tab` and `_on_url_start`**

Replace the existing `_make_youtube_tab` method:

```python
    def _make_youtube_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("YouTube URL, or type a search")
        self._url_start_btn = QPushButton("Start")
        self._url_start_btn.clicked.connect(self._on_url_start)
        row.addWidget(self._url_input)
        row.addWidget(self._url_start_btn)
        self._url_error = QLabel("")
        self._url_error.setStyleSheet("color: red;")
        layout.addLayout(row)
        layout.addWidget(self._url_error)
        self._results_list = QListWidget()
        self._results_list.setVisible(False)
        self._results_list.itemActivated.connect(self._on_result_activated)
        layout.addWidget(self._results_list)
        self._search_worker: SearchWorker | None = None
        return w
```

Replace the existing `_on_url_start` method:

```python
    def _on_url_start(self):
        text = self._url_input.text().strip()
        if not text:
            return
        if is_valid_youtube_url(text):
            self._url_error.setStyleSheet("color: red;")
            self._url_error.setText("")
            self._results_list.setVisible(False)
            track_name = text.split("v=")[-1] if "v=" in text else text.split("/")[-1]
            self.start_pipeline.emit(text, track_name, True)
            return
        self._url_error.setStyleSheet("color: black;")
        self._url_error.setText("Searching…")
        self._url_start_btn.setEnabled(False)
        self._search_worker = SearchWorker(text)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()
```

Add three new methods directly after `_on_url_start`:

```python
    def _on_search_finished(self, results: list) -> None:
        self._url_start_btn.setEnabled(True)
        if not results:
            self._url_error.setStyleSheet("color: red;")
            query = self._url_input.text().strip()
            self._url_error.setText(f"No results found for '{query}'")
            self._results_list.setVisible(False)
            return
        self._url_error.setText("")
        self._results_list.clear()
        for result in results:
            minutes, seconds = divmod(result.duration_seconds, 60)
            item = QListWidgetItem(f"{result.title} — {result.channel} — {minutes}:{seconds:02d}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self._results_list.addItem(item)
        self._results_list.setVisible(True)

    def _on_search_error(self, message: str) -> None:
        self._url_start_btn.setEnabled(True)
        self._url_error.setStyleSheet("color: red;")
        self._url_error.setText(f"Search failed: {message}")
        self._results_list.setVisible(False)

    def _on_result_activated(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.ItemDataRole.UserRole)
        url, track_name, is_url = _build_pipeline_args(result)
        self._results_list.setVisible(False)
        self._results_list.clear()
        self.start_pipeline.emit(url, track_name, is_url)
```

- [ ] **Step 3: Run the full test suite to confirm no regressions**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all existing tests still PASS, plus Task 1–3 tests

- [ ] **Step 4: Manually smoke-test text-only search**

```bash
.venv/bin/python -m stem_splitter.main
```

Verify:
1. Pasting a real YouTube URL into the field and clicking Start behaves exactly as before (starts the pipeline immediately, no results list shown)
2. Typing a search term (e.g. an artist name) and clicking Start shows "Searching…" then a populated results list below the field
3. Typing a nonsense query that returns no matches shows "No results found for '...'" and no list
4. Double-clicking a result starts the pipeline (progress panel appears) and hides the results list
5. Pressing Enter in the field triggers the same Start behavior as clicking the button (existing `QLineEdit` behavior — confirm it still works)

- [ ] **Step 5: Commit**

```bash
git add stem_splitter/ui/source_panel.py
git commit -m "feat: wire YouTube search results list into SourcePanel"
```

---

### Task 5: Thumbnail loading

**Files:**
- Modify: `stem_splitter/ui/source_panel.py`

**Interfaces:**
- Consumes: `self._results_list` and the per-result `QListWidgetItem`s from Task 4
- Produces: each result row's icon is set asynchronously once its thumbnail downloads

- [ ] **Step 1: Add required imports**

Add to `stem_splitter/ui/source_panel.py`:

```python
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
```

- [ ] **Step 2: Create the network manager and wire it into `_make_youtube_tab`**

In `_make_youtube_tab`, add this line right before `return w`:

```python
        self._network_manager = QNetworkAccessManager(self)
```

- [ ] **Step 3: Call thumbnail loading from `_on_search_finished`**

In `_on_search_finished`, inside the `for result in results:` loop, add a call right after `self._results_list.addItem(item)`:

```python
            self._results_list.addItem(item)
            self._load_thumbnail(item, result.thumbnail_url)
```

- [ ] **Step 4: Add `_load_thumbnail` and `_on_thumbnail_loaded`**

Add these two methods after `_on_result_activated`:

```python
    def _load_thumbnail(self, item: QListWidgetItem, thumbnail_url: str) -> None:
        if not thumbnail_url:
            return
        reply = self._network_manager.get(QNetworkRequest(QUrl(thumbnail_url)))
        reply.finished.connect(lambda: self._on_thumbnail_loaded(item, reply))

    def _on_thumbnail_loaded(self, item: QListWidgetItem, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll().data())
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
        reply.deleteLater()
```

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all tests still PASS (thumbnail loading has no automated test — it's a live network call, verified manually below, consistent with this codebase's existing convention of not instantiating live Qt widget/network behavior in tests)

- [ ] **Step 6: Manually smoke-test thumbnails and the full end-to-end flow**

```bash
.venv/bin/python -m stem_splitter.main
```

Verify:
1. Searching a term shows the results list immediately with text, and thumbnail images pop in shortly after for each row
2. A result whose thumbnail fails to load (e.g. temporarily disconnect network mid-search) still shows its text row with no icon — doesn't block or hide other rows
3. Double-clicking a result with a loaded thumbnail still starts the pipeline correctly (thumbnail loading doesn't interfere with `itemActivated`)
4. Full flow end-to-end: search → pick a result → pipeline downloads, separates, and the stem player opens with the correct track name (check the output folder name matches the sanitized video title, not the raw title with any `/` in it if you picked one containing a slash)

- [ ] **Step 7: Commit**

```bash
git add stem_splitter/ui/source_panel.py
git commit -m "feat: load search result thumbnails asynchronously"
```
