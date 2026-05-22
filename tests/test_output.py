from pathlib import Path
import pytest
from stem_splitter.core.output import make_output_dir, stem_paths, midi_path, STEMS

def test_stems_list():
    assert STEMS == ["vocals", "drums", "bass", "guitar", "piano", "other"]

def test_make_output_dir_creates_directory(tmp_path):
    result = make_output_dir("My Song", base_dir=tmp_path)
    assert result == tmp_path / "My Song"
    assert result.is_dir()

def test_make_output_dir_handles_collision(tmp_path):
    (tmp_path / "My Song").mkdir()
    result = make_output_dir("My Song", base_dir=tmp_path)
    assert result == tmp_path / "My Song (2)"
    assert result.is_dir()

def test_make_output_dir_handles_multiple_collisions(tmp_path):
    (tmp_path / "My Song").mkdir()
    (tmp_path / "My Song (2)").mkdir()
    result = make_output_dir("My Song", base_dir=tmp_path)
    assert result == tmp_path / "My Song (3)"
    assert result.is_dir()

def test_stem_paths_returns_all_six(tmp_path):
    paths = stem_paths(tmp_path)
    assert set(paths.keys()) == set(STEMS)
    assert all(p.parent == tmp_path for p in paths.values())
    assert all(p.suffix == ".wav" for p in paths.values())

def test_midi_path(tmp_path):
    assert midi_path(tmp_path, "bass") == tmp_path / "bass.mid"

def test_midi_path_raises_for_unknown_stem(tmp_path):
    with pytest.raises(ValueError, match="Unknown stem"):
        midi_path(tmp_path, "saxophone")
