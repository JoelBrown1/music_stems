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
