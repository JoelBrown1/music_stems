# tests/test_player_window.py
import pytest
from stem_splitter.ui.player_window import (
    _measure_fractions, _beat_fractions,
    _to_screen, _to_fraction, _zoom_centered, _clamp_window,
    _nearest_beat_fraction, _should_snap, _MIN_SPAN,
)


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


# --- _to_screen ---

def test_to_screen_maps_zero():
    assert _to_screen(0.0, 0.0, 1.0, 800) == 0


def test_to_screen_maps_one():
    assert _to_screen(1.0, 0.0, 1.0, 800) == 800


def test_to_screen_maps_midpoint():
    assert _to_screen(0.5, 0.0, 1.0, 800) == 400


def test_to_screen_zoomed_left_edge():
    # view [0.25, 0.75]: fraction 0.25 → x=0
    assert _to_screen(0.25, 0.25, 0.75, 800) == 0


def test_to_screen_zoomed_right_edge():
    # view [0.25, 0.75]: fraction 0.75 → x=800
    assert _to_screen(0.75, 0.25, 0.75, 800) == 800


def test_to_screen_zoomed_midpoint():
    # view [0.25, 0.75]: fraction 0.5 → x=400
    assert _to_screen(0.5, 0.25, 0.75, 800) == 400


# --- _to_fraction ---

def test_to_fraction_maps_zero():
    assert _to_fraction(0.0, 0.0, 1.0, 800) == pytest.approx(0.0)


def test_to_fraction_maps_full_width():
    assert _to_fraction(800.0, 0.0, 1.0, 800) == pytest.approx(1.0)


def test_to_fraction_zoomed_left_edge():
    # view [0.25, 0.75]: x=0 → fraction 0.25
    assert _to_fraction(0.0, 0.25, 0.75, 800) == pytest.approx(0.25)


def test_to_fraction_zoomed_right_edge():
    # view [0.25, 0.75]: x=800 → fraction 0.75
    assert _to_fraction(800.0, 0.25, 0.75, 800) == pytest.approx(0.75)


# --- _zoom_centered ---

def test_zoom_centered_2x_around_center():
    # factor=0.5 (zoom in 2×) around 0.5 from full view
    s, e = _zoom_centered(0.0, 1.0, 0.5, 0.5)
    assert s == pytest.approx(0.25)
    assert e == pytest.approx(0.75)


def test_zoom_centered_zoom_out_to_full():
    # factor=2.0 (zoom out) from half-view centered at 0.5
    s, e = _zoom_centered(0.25, 0.75, 2.0, 0.5)
    assert s == pytest.approx(0.0)
    assert e == pytest.approx(1.0)


def test_zoom_centered_clamps_minimum_span():
    # Extreme zoom in must not produce span below _MIN_SPAN
    s, e = _zoom_centered(0.499, 0.501, 0.001, 0.5)
    assert (e - s) == pytest.approx(_MIN_SPAN)


def test_zoom_centered_stays_within_bounds():
    # Zooming near the left edge must not go negative
    s, e = _zoom_centered(0.0, 0.1, 0.5, 0.0)
    assert s >= 0.0
    assert e <= 1.0


# --- _clamp_window ---

def test_clamp_window_no_change():
    s, e = _clamp_window(0.2, 0.8)
    assert s == pytest.approx(0.2)
    assert e == pytest.approx(0.8)


def test_clamp_window_left_overflow():
    s, e = _clamp_window(-0.1, 0.4)
    assert s == pytest.approx(0.0)
    assert e == pytest.approx(0.5)


def test_clamp_window_right_overflow():
    s, e = _clamp_window(0.7, 1.1)
    assert e == pytest.approx(1.0)
    assert s == pytest.approx(0.6)


# --- _nearest_beat_fraction ---

def test_nearest_beat_fraction_on_beat():
    # 120 bpm, 60s song: beat at 0.5s = fraction 0.5/60
    beat_frac = 0.5 / 60.0
    assert _nearest_beat_fraction(beat_frac, 120.0, 60.0) == pytest.approx(beat_frac, abs=1e-6)


def test_nearest_beat_fraction_snaps_to_nearest():
    # 120 bpm, 60s song: beat at 1.0s = fraction 1/60; slightly off
    result = _nearest_beat_fraction(1.02 / 60.0, 120.0, 60.0)
    assert result == pytest.approx(1.0 / 60.0, abs=1e-4)


def test_nearest_beat_fraction_zero_bpm_returns_unchanged():
    assert _nearest_beat_fraction(0.5, 0.0, 60.0) == pytest.approx(0.5)


# --- _should_snap ---

def test_should_snap_within_threshold():
    # fraction and nearest 5px apart at 800px width → snap
    assert _should_snap(0.0, 5.0 / 800.0, 0.0, 1.0, 800) is True


def test_should_snap_outside_threshold():
    # fraction and nearest 15px apart → no snap
    assert _should_snap(0.0, 15.0 / 800.0, 0.0, 1.0, 800) is False
