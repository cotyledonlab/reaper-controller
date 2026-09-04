"""File-drop bridge client tests — fake responder, no REAPER needed."""

import json
import threading

import pytest

from reaper_connector import bridge as B


@pytest.fixture()
def respath(tmp_path, monkeypatch):
    monkeypatch.setenv("REAPER_RESOURCE_PATH", str(tmp_path))
    (tmp_path / "AgentBridge" / "in").mkdir(parents=True)
    (tmp_path / "AgentBridge" / "out").mkdir(parents=True)
    (tmp_path / "AgentBridge" / "log").mkdir(parents=True)
    return tmp_path


def _responder(respath, handler, stop):
    in_d, out_d = respath / "AgentBridge" / "in", respath / "AgentBridge" / "out"
    while not stop.is_set():
        for req in in_d.glob("*.json"):
            oid = req.stem
            if (out_d / f"{oid}.json").exists():
                continue
            try:
                payload = json.loads(req.read_text())
            except (OSError, ValueError):
                continue
            reply = handler(payload)
            tmp = out_d / f"{oid}.json.tmp"
            tmp.write_text(json.dumps(reply))
            tmp.rename(out_d / f"{oid}.json")
        stop.wait(0.01)


def _serve(respath, handler):
    stop = threading.Event()
    t = threading.Thread(target=_responder, args=(respath, handler, stop), daemon=True)
    t.start()
    return stop


def test_ping_roundtrip(respath):
    stop = _serve(
        respath,
        lambda p: {"v": 1, "op_id": p["op_id"], "ok": True,
                   "result": {"pong": True}, "adapter": "fake", "evidence": []},
    )
    try:
        reply = B.send("ping", timeout=5.0)
    finally:
        stop.set()
    assert reply["ok"] is True
    assert reply["result"] == {"pong": True}


def test_daemon_error_surfaces_as_bridge_error(respath):
    stop = _serve(
        respath,
        lambda p: {"v": 1, "op_id": p["op_id"], "ok": False,
                   "error": {"code": "UNKNOWN_OP", "detail": "no such op"}},
    )
    try:
        with pytest.raises(B.BridgeError) as ei:
            B.send("bogus", timeout=5.0)
    finally:
        stop.set()
    assert ei.value.code == "UNKNOWN_OP"


def test_timeout_without_daemon(respath):
    with pytest.raises(B.BridgeTimeout):
        B.send("ping", timeout=0.4)


def test_missing_dirs_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("REAPER_RESOURCE_PATH", str(tmp_path / "nope"))
    with pytest.raises(FileNotFoundError):
        B.send("ping", timeout=0.2)
