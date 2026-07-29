# YouTube Search Design

**Date:** 2026-07-28  
**Status:** Approved

## Summary

Let the user find a video by typing a search term (e.g. an artist/song name) into the existing YouTube tab's field, instead of requiring an exact URL. The same field is reused: if the text is a valid YouTube URL, behavior is unchanged; otherwise it's treated as a search query, and a results list (thumbnail + title/channel/duration) appears for the user to pick from. Selecting a result starts the pipeline exactly as pasting its URL would today. Search is implemented via the already-bundled `yt-dlp` binary — no new dependency, no API key.

## Architecture

Follows the existing four-layer architecture (core never imports UI).

**Modified files:**
- `stem_splitter/core/downloader.py` — add `SearchResult` dataclass + `search_youtube()`
- `stem_splitter/core/worker.py` — add `SearchWorker(QThread)`
- `stem_splitter/ui/source_panel.py` — YouTube tab gains a results list and search branch

No changes to `PipelineWorker`, `separator.py`, or anything downstream of "we have a URL" — the search feature only produces a URL + track name, then hands off to the exact same pipeline start path used today.

## Components

### `search_youtube()` (`stem_splitter/core/downloader.py`)

```python
@dataclass
class SearchResult:
    video_id: str
    title: str
    channel: str
    duration_seconds: int
    thumbnail_url: str
    url: str  # https://www.youtube.com/watch?v=<video_id>

def search_youtube(query: str, max_results: int = 5) -> list[SearchResult]:
    # subprocess.run([_YT_DLP, f"ytsearch{max_results}:{query}",
    #                 "--dump-json", "--flat-playlist", "--skip-download"])
    # parses one JSON object per line into SearchResult
```

Lives alongside `is_valid_youtube_url` / `download_audio` rather than a new file — same "talk to yt-dlp about YouTube content" purpose, and the file is small enough that splitting it would be premature.

### `SearchWorker` (`stem_splitter/core/worker.py`)

Same shape as `PipelineWorker`/`MidiWorker`:

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

### `SourcePanel` changes (`stem_splitter/ui/source_panel.py`)

- `_on_url_start` branches on `is_valid_youtube_url(text)`:
  - **Valid URL** → unchanged: emits `start_pipeline` immediately.
  - **Non-empty, not a URL** → disable `_url_start_btn`, set `_url_error` to `"Searching…"`, launch `SearchWorker`.
- New `self._results_list: QListWidget`, hidden until results arrive, added below the URL row.
- On `SearchWorker.finished(results)`:
  - Clear/hide list if `results` is empty, set `_url_error` to `"No results found for '<query>'"`.
  - Otherwise populate `QListWidgetItem`s with text `"{title} — {channel} — {duration}"`, show the list, re-enable the Start button, clear `_url_error`.
  - For each item, kick off an async thumbnail fetch (see below) and call `item.setIcon(...)` when it lands.
- On `SearchWorker.error(message)`: re-enable Start button, set `_url_error` to `"Search failed: {message}"`.
- `itemActivated` (covers double-click and Enter) on a result:
  - Build `(result.url, _sanitize_track_name(result.title), True)` — the same 3-tuple shape `_on_url_start` builds for a pasted URL — and emit `start_pipeline`.
  - Clear and hide the results list.

### Track name sanitization

`make_output_dir()` (`stem_splitter/core/output.py`) does no sanitization today — it works because URL-derived track names (`url.split("v=")[-1]`, a video ID) are already filesystem-safe. A real video title is not: e.g. `"AC/DC - Back In Black (Official Video)"` contains `/`, which `base_dir / track_name` would silently turn into a nested directory instead of a single track folder. New module-level helper in `source_panel.py` (small, single call site — not worth a shared module):

```python
import re

def _sanitize_track_name(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", title).strip()
```

### Thumbnail loading

Per-row, via `QNetworkAccessManager` (`PyQt6.QtNetwork`, no new dependency): issue a GET for `thumbnail_url`, and on `finished`, decode the reply bytes into a `QPixmap`/`QIcon` and set it on the corresponding `QListWidgetItem`. Fully async — the results list renders immediately with text, thumbnails pop in as they arrive.

## Data Flow

```
User types text, clicks Start (or presses Enter)
  → is_valid_youtube_url(text)?
      YES → start_pipeline.emit(text, track_name_from_url, True)   [unchanged]
      NO, non-empty →
        SearchWorker(text).start()
          → search_youtube(text) via yt-dlp ytsearch5:
          → finished(list[SearchResult]) or error(str)
        → populate QListWidget (text now, thumbnails async via QNetworkAccessManager)
        → user double-clicks / Enters a result
          → start_pipeline.emit(result.url, _sanitize_track_name(result.title), True)
```

From `start_pipeline` onward, behavior is identical regardless of whether the URL came from pasting or from search — `MainWindow._on_start_pipeline` and `PipelineWorker` are untouched.

## Validation

- Empty input on Start: no-op, same as today (no error shown for blank field).
- `max_results` fixed at 5 — not user-configurable in this iteration.

## Error Handling

| Scenario | Behavior |
|---|---|
| yt-dlp search fails (network down, non-zero exit) | Inline red label: `"Search failed: {message}"`. No popup — matches existing "Invalid YouTube URL" inline error pattern. |
| Zero results | Inline label: `"No results found for '{query}'"`. Results list stays hidden. |
| Thumbnail fetch fails for one row | Non-fatal — that row keeps a blank/placeholder icon. Doesn't block the rest of the list or surface an error. |
| Search in progress | Start button disabled; re-enabled once results or an error arrive. |

## Testing

Follows `tests/test_downloader.py` conventions (mock `subprocess.run`, assert on args and parsing):

- `search_youtube()`: mock `subprocess.run` to return canned yt-dlp JSON-lines output → assert correct `SearchResult` list (title/channel/duration/id/thumbnail parsed correctly) and assert CLI args include `ytsearch5:<query>`, `--dump-json`, `--flat-playlist`, `--skip-download`.
- Zero-results case (empty yt-dlp stdout) → returns `[]`, not an error.
- yt-dlp non-zero exit → raises `CalledProcessError`, same as the existing `download_audio` test.
- `SourcePanel`: a light test verifying that activating a result item emits `start_pipeline` with the expected `(url, track_name, True)` tuple.
- `_sanitize_track_name()`: asserts `/`, `\`, `:`, etc. are replaced, e.g. `"AC/DC - Back In Black"` → `"AC_DC - Back In Black"`.

## Out of Scope

- Making `max_results` user-configurable
- Caching search results or thumbnails across sessions
- Searching sources other than YouTube
- Changing how pasted-URL track naming works (still derived from the URL, not a fetched title)
