from dataclasses import dataclass


@dataclass
class MidiParams:
    onset_threshold: float = 0.50
    frame_threshold: float = 0.30
    minimum_note_length: int = 58
    minimum_frequency: float = 40.0
    maximum_frequency: float = 8000.0
    melodia_trick: bool = False
    sensitivity: float = 0.50


DEFAULTS: dict[str, MidiParams] = {
    "vocals": MidiParams(
        onset_threshold=0.50,
        frame_threshold=0.30,
        minimum_note_length=80,
        minimum_frequency=80.0,
        maximum_frequency=1200.0,
        melodia_trick=True,
    ),
    "bass": MidiParams(
        onset_threshold=0.40,
        frame_threshold=0.25,
        minimum_note_length=100,
        minimum_frequency=40.0,
        maximum_frequency=300.0,
        melodia_trick=False,
    ),
    "guitar": MidiParams(
        onset_threshold=0.50,
        frame_threshold=0.30,
        minimum_note_length=58,
        minimum_frequency=80.0,
        maximum_frequency=1200.0,
        melodia_trick=True,
    ),
    "other": MidiParams(
        onset_threshold=0.50,
        frame_threshold=0.30,
        minimum_note_length=58,
        minimum_frequency=40.0,
        maximum_frequency=8000.0,
        melodia_trick=False,
    ),
    "drums": MidiParams(sensitivity=0.50),
    "piano": MidiParams(),
}
