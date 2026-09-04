"""midi queue tests — virtual CoreMIDI port, no DAW needed."""
import threading
import pytest
midi = pytest.importorskip("reaper_connector.midi")


@pytest.fixture()
def serve(tmp_path, monkeypatch):
    monkeypatch.setenv("REAPER_RESOURCE_PATH", str(tmp_path))
    for d in ("in", "out", "log", "midi-in", "midi-out"):
        (tmp_path / "AgentBridge" / d).mkdir(parents=True)
    th = threading.Thread(target=midi.serve_forever, daemon=True)
    th.start()
    import time
    for _ in range(100):
        if midi.serve_alive():
            break
        time.sleep(0.05)
    assert midi.serve_alive()
    return tmp_path


def test_enqueue_receipt(serve):
    notes = [{"pitch": 60, "start_beats": 0, "dur_beats": 0.25, "vel": 90}]
    receipt = midi.enqueue_phrase(notes, tempo=240, timeout=15)
    assert receipt["ok"] is True
    assert receipt["notes"] == 1


def test_no_daemon_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("REAPER_RESOURCE_PATH", str(tmp_path))
    (tmp_path / "AgentBridge" / "midi-in").mkdir(parents=True)
    (tmp_path / "AgentBridge" / "midi-out").mkdir(parents=True)
    with pytest.raises(RuntimeError):
        midi.enqueue_phrase([{"pitch": 60, "start_beats": 0, "dur_beats": 1}], timeout=1)
