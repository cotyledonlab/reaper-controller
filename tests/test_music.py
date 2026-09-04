"""music.py unit tests — pitch math against known spellings, no DAW."""

import pytest

from reaper_connector import music as M


def test_parse_note():
    assert M.parse_note("C4") == 60
    assert M.parse_note("A4") == 69
    assert M.parse_note("C#4") == 61
    assert M.parse_note("Db4") == 61
    assert M.parse_note("c3") == 48
    with pytest.raises(ValueError):
        M.parse_note("H4")
    with pytest.raises(ValueError):
        M.parse_note("C")


def test_chord_spellings():
    assert M.chord_pitches("C4", "maj") == [60, 64, 67]
    assert M.chord_pitches("A3", "min") == [57, 60, 64]
    assert M.chord_pitches("B3", "dim") == [59, 62, 65]
    assert M.chord_pitches("C4", "maj7") == [60, 64, 67, 71]
    assert M.chord_pitches("D4", "dom7") == [62, 66, 69, 72]
    with pytest.raises(ValueError):
        M.chord_pitches("C4", "maj9")


def test_first_inversion():
    assert M.chord_pitches("C4", "maj", inversion=1) == [64, 67, 72]
    assert M.chord_pitches("C4", "maj", inversion=2) == [67, 72, 76]


def test_progression_default_loop():
    notes = M.progression()  # vi-IV-I-V in C
    assert len(notes) == 12  # 4 chords x triad
    roots = [n["pitch"] for n in notes[::3]]
    assert roots == [57, 53, 48, 55]  # A3 F3 C3 G3
    starts = sorted({n["start_beats"] for n in notes})
    assert starts == [0, 4, 8, 12]
    assert all(n["dur_beats"] == 4 for n in notes)


def test_progression_minor():
    notes = M.progression("A3", ["i", "VI", "VII"], mode="minor", beats_each=2)
    assert len(notes) == 9
    assert [n["pitch"] for n in notes[::3]] == [45, 53, 55]  # A2 F3 G3


def test_strum_shape():
    notes = M.strum([60, 64, 67], stagger_beats=0.1)
    assert [n["pitch"] for n in notes] == [60, 64, 67]
    assert [n["start_beats"] for n in notes] == pytest.approx([0, 0.1, 0.2])
    assert notes[0]["vel"] > notes[-1]["vel"]  # downstroke decays
    up = M.strum([60, 64, 67], direction="up", stagger_beats=0.1)
    assert [n["pitch"] for n in up] == [67, 64, 60]


def test_bassline():
    notes = M.bassline("C2", bars=1)
    assert [(n["pitch"], n["start_beats"]) for n in notes] == [
        (36, 0),
        (43, 1),
        (36, 2),
        (43, 3),
    ]


def test_compose_dispatcher():
    assert len(M.compose_part({"shape": "chord", "root": "C4"})) == 3
    assert len(M.compose_part({"shape": "progression"})) == 12
    strummed = M.compose_part({"shape": "strum", "root": "G3", "quality": "maj"})
    assert [n["pitch"] for n in strummed] == [55, 59, 62]
    assert len(M.compose_part({"shape": "bass", "bars": 2})) == 8
    with pytest.raises(ValueError):
        M.compose_part({"shape": "solo"})
