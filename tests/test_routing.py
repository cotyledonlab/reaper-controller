"""Routing-reader tests over the live t5 fixture (committed RPP)."""

from pathlib import Path

from reaper_connector import rpp as R

FIX = Path(__file__).resolve().parent / "fixtures" / "t5-routing.RPP"


def test_fixture_reads_clean():
    info = R.read(FIX)
    assert info["warnings"] == []
    assert info["tempo"] == 120
    assert [t["name"] for t in info["tracks"]] == ["AgentSynth", "AgentBus"]


def test_folder_depths():
    info = R.read(FIX)
    depths = [(t["name"], t["folder_depth"]) for t in info["tracks"]]
    assert depths == [("AgentSynth", 1), ("AgentBus", -1)]


def test_send_visible_as_receive_and_derived_send():
    info = R.read(FIX)
    bus = info["tracks"][1]
    assert len(bus["receives"]) == 1
    assert bus["receives"][0]["src_track"] == 0
    assert bus["receives"][0]["volume"] == 0.8
    assert info["tracks"][0]["receives"] == []
    assert info["sends"] == [{"from": 0, "to": 1, "volume": 0.8}]


def test_marker_and_selection():
    info = R.read(FIX)
    assert info["markers"] == [{"number": 1, "position_sec": 8.0, "name": "chorus"}]
    assert info["selection"] == [0.0, 4.0]


def test_take_lanes_selected_wins(tmp_path):
    rpp = tmp_path / "takes.RPP"
    rpp.write_text(
        "<REAPER_PROJECT 0.1 x 0 0\n"
        "  TEMPO 120 4 4 0\n"
        "  <TRACK {A}\n"
        "    NAME T\n"
        "    <ITEM\n"
        "      POSITION 0\n"
        "      LENGTH 4\n"
        "      <SOURCE MIDI\n"
        "        E 0 90 3c 40\n"
        "        E 960 80 3c 00\n"
        "      >\n"
        "      TAKE SEL\n"
        "      NAME rec-take\n"
        "      <SOURCE MIDI\n"
        "        E 0 90 40 50\n"
        "        E 960 80 40 00\n"
        "      >\n"
        "    >\n"
        "  >\n"
        ">\n"
    )
    info = R.read(rpp)
    item = info["tracks"][0]["items"][0]
    assert [t["name"] for t in item["takes"]] == [None, "rec-take"]
    assert [t["selected"] for t in item["takes"]] == [None, True]
    assert [n["pitch"] for n in item["notes"]] == [64]  # selected take plays


def test_live_take_file_takes_visible():
    import pathlib

    ref = pathlib.Path(__file__).resolve().parents[1] / "scratch" / "t6-take.RPP"
    if not ref.is_file():
        pytest.skip("no live take yet")
    info = R.read(ref)
    takes = info["tracks"][2]["items"][0]["takes"]
    assert len(takes) >= 2
    assert takes[0]["notes"] != []  # original progression survives
    live = [t for t in takes if t["name"] == "03-PlayerKeys-MIDI" and t["notes"]]
    assert live, "a recorded take with live notes exists"
    assert [n["pitch"] for n in live[0]["notes"]][:4] == [76, 79, 81, 84]
