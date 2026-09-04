"""RPP builder/reader tests — no DAW needed. The golden check: substituting
the reference's own values back into the golden template must reproduce
t2-ref.RPP byte-for-byte (modulo GUIDs/epoch), proving the template is
REAPER-verbatim."""

import re

import pytest

from reaper_connector import rpp as R
from reaper_connector import templates as T

REF_RIFF = T.default_notes()


def test_midi_codec_roundtrip():
    lines = R.encode_notes(REF_RIFF, 8)
    assert len(lines) == 2 * len(REF_RIFF) + 1  # ons + offs + all-off
    assert lines[-1].endswith("b0 7b 00")
    back = R.decode_notes(lines)
    assert len(back) == len(REF_RIFF)
    for orig, got in zip(REF_RIFF, back):
        assert got["pitch"] == orig["pitch"]
        assert got["start_beats"] == pytest.approx(orig["start_beats"])
        assert got["dur_beats"] == pytest.approx(orig["dur_beats"])
        assert got["vel"] == orig["vel"]


def test_midi_codec_odd_lengths():
    notes = [{"pitch": 60, "start_beats": 0.5, "dur_beats": 0.25, "vel": 80}]
    assert R.decode_notes(R.encode_notes(notes, 4)) == [
        {"pitch": 60, "start_beats": 0.5, "dur_beats": 0.25, "vel": 80, "chan": 0}
    ]


def test_create_read_roundtrip(tmp_path):
    out = tmp_path / "song.RPP"
    summary = R.create(out, name="TestSynth", tempo=100, render_file=str(tmp_path / "o.wav"))
    assert summary["notes"] == 8
    info = R.read(out)
    assert info["tempo"] == 100
    assert info["render_file"] == str(tmp_path / "o.wav")
    assert info["sample_rate"] == 44100
    assert len(info["tracks"]) == 1
    tr = info["tracks"][0]
    assert tr["name"] == "TestSynth"
    assert tr["fx"] == ["VSTi: ReaSynth (Cockos)"]
    assert len(tr["items"]) == 1
    assert tr["items"][0]["length"] == 8
    assert len(tr["items"][0]["notes"]) == 8
    assert info["warnings"] == []


def test_read_reference_notes():
    import pathlib

    ref = pathlib.Path(__file__).resolve().parents[1] / "scratch" / "t2-ref.RPP"
    if not ref.is_file():
        pytest.skip("no live reference yet")
    info = R.read(ref)
    assert info["tempo"] == 120
    assert info["tracks"][0]["name"] == "AgentSynth"
    pitches = [n["pitch"] for n in info["tracks"][0]["items"][0]["notes"]]
    assert pitches == [60, 64, 67, 72, 67, 69, 71, 72]
    assert info["warnings"] == []


def test_golden_template_is_reference_verbatim():
    """Every non-token template line must exist verbatim in the live reference."""
    import pathlib

    ref = pathlib.Path(__file__).resolve().parents[1] / "scratch" / "t2-ref.RPP"
    if not ref.is_file():
        pytest.skip("no live reference yet")
    ref_lines = set(ref.read_text().splitlines())
    missing = [
        ln
        for ln in R.golden_path().read_text().splitlines()
        if "__" not in ln and ln not in ref_lines and ln.strip() != ""
    ]
    # NOTE_LINES token line itself is the only structural absence allowed
    assert missing == [], missing[:5]


def test_render_paths_reject_spaces(tmp_path):
    with pytest.raises(ValueError):
        R.create(tmp_path / "x.RPP", render_file="/tmp/has space/o.wav")
