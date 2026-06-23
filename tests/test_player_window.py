# tests/test_player_window.py
from stem_splitter.ui.player_window import _measure_fractions, _beat_fractions


# --- _measure_fractions ---

def test_measure_fractions_zero_bpm_returns_empty():
    assert _measure_fractions(0.0, 4, 60.0) == []


def test_measure_fractions_zero_duration_returns_empty():
    assert _measure_fractions(120.0, 4, 0.0) == []


def test_measure_fractions_first_entry_is_zero_measure_one():
    result = _measure_fractions(120.0, 4, 10.0)
    assert result[0] == (0.0, 1)


def test_measure_fractions_120bpm_4_4_spacing():
    # 120 BPM, 4/4: seconds_per_beat=0.5, seconds_per_measure=2.0
    # In 10s: boundaries at t=0, 2, 4, 6, 8, 10 → fractions 0.0, 0.2, 0.4, 0.6, 0.8, 1.0
    result = _measure_fractions(120.0, 4, 10.0)
    fracs = [f for f, _ in result]
    assert abs(fracs[1] - 0.2) < 0.001
    assert abs(fracs[2] - 0.4) < 0.001


def test_measure_fractions_measure_numbers_increment():
    result = _measure_fractions(120.0, 4, 10.0)
    nums = [n for _, n in result]
    assert nums[0] == 1
    assert nums[1] == 2
    assert nums[2] == 3


def test_measure_fractions_3_4_time():
    # 120 BPM, 3/4: seconds_per_measure=1.5
    # In 6s: boundaries at t=0, 1.5, 3.0, 4.5, 6.0 → 5 entries
    result = _measure_fractions(120.0, 3, 6.0)
    assert len(result) == 5
    assert abs(result[1][0] - 0.25) < 0.001  # 1.5 / 6.0 = 0.25


def test_measure_fractions_no_fraction_above_one():
    result = _measure_fractions(60.0, 4, 3.0)
    # 60 BPM, 4/4: seconds_per_measure=4.0; only t=0 fits in 3s
    assert all(f <= 1.0 for f, _ in result)
    assert len(result) == 1


# --- _beat_fractions ---

def test_beat_fractions_zero_bpm_returns_empty():
    assert _beat_fractions(0.0, 4, 60.0) == []


def test_beat_fractions_zero_duration_returns_empty():
    assert _beat_fractions(120.0, 4, 0.0) == []


def test_beat_fractions_excludes_measure_boundaries():
    # 120 BPM, 4/4, 10s: measure boundaries at fractions 0.0, 0.2, 0.4, 0.6, 0.8, 1.0
    result = _beat_fractions(120.0, 4, 10.0)
    measure_fracs = {f for f, _ in _measure_fractions(120.0, 4, 10.0)}
    for frac in result:
        assert not any(abs(frac - mf) < 0.001 for mf in measure_fracs)


def test_beat_fractions_count_120bpm_4_4_10s():
    # 120 BPM, 4/4, 10s: 19 beats at t=0.5..9.5; 4 are measure boundaries (t=2,4,6,8)
    # Non-boundary count: 19 - 4 = 15
    result = _beat_fractions(120.0, 4, 10.0)
    assert len(result) == 15


def test_beat_fractions_all_within_zero_one():
    result = _beat_fractions(120.0, 4, 10.0)
    assert all(0.0 < f < 1.0 for f in result)


def test_beat_fractions_3_4_time():
    # 120 BPM, 3/4, 6s: beats at t=0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5
    # Measure boundaries: t=0,1.5,3.0,4.5,6.0 → beat_index%3==0: indices 3,6,9
    # Non-boundary: 11 total - 3 = 8
    result = _beat_fractions(120.0, 3, 6.0)
    assert len(result) == 8
