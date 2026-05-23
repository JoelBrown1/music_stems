from stem_splitter.core.midi_params import MidiParams, DEFAULTS


def test_midi_params_class_defaults():
    p = MidiParams()
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 58
    assert p.minimum_frequency == 40.0
    assert p.maximum_frequency == 8000.0
    assert p.melodia_trick is False
    assert p.sensitivity == 0.50


def test_defaults_vocals():
    p = DEFAULTS["vocals"]
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 80
    assert p.minimum_frequency == 80.0
    assert p.maximum_frequency == 1200.0
    assert p.melodia_trick is True


def test_defaults_bass():
    p = DEFAULTS["bass"]
    assert p.onset_threshold == 0.40
    assert p.frame_threshold == 0.25
    assert p.minimum_note_length == 100
    assert p.minimum_frequency == 40.0
    assert p.maximum_frequency == 300.0
    assert p.melodia_trick is False


def test_defaults_guitar():
    p = DEFAULTS["guitar"]
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 58
    assert p.minimum_frequency == 80.0
    assert p.maximum_frequency == 1200.0
    assert p.melodia_trick is True


def test_defaults_other():
    p = DEFAULTS["other"]
    assert p.onset_threshold == 0.50
    assert p.frame_threshold == 0.30
    assert p.minimum_note_length == 58
    assert p.minimum_frequency == 40.0
    assert p.maximum_frequency == 8000.0
    assert p.melodia_trick is False


def test_defaults_drums():
    p = DEFAULTS["drums"]
    assert p.sensitivity == 0.50


def test_defaults_piano():
    assert "piano" in DEFAULTS


def test_defaults_covers_all_stems():
    for stem in ["vocals", "bass", "guitar", "other", "drums", "piano"]:
        assert stem in DEFAULTS
