"""Live MIDI play-in over a CoreMIDI virtual port (no IAC setup needed).

`PlayerOut` opens a virtual source named `reaper-connector` that appears in
REAPER's track-input list (MIDI → reaper-connector → All channels). One-time
human step: select it as the armed track's input; the agent owns arm/monitor
(via `player.rec_arm`), transport (OSC `/record`), and the notes themselves.
Requires the `midi` extra (mido + python-rtmidi).
"""

from __future__ import annotations

import time

PORT_NAME = "reaper-connector"

# File-drop queue so many short-lived agent calls share ONE virtual port
# (CoreMIDI endpoint identity matters: REAPER opens the port the server
# holds; transient per-send ports are never the mapped one).
QUEUE_IN = "midi-in"
QUEUE_OUT = "midi-out"
SERVE_HEARTBEAT = "midi-serve.heartbeat"
HEARTBEAT_EVERY_S = 2.0


def _mido():
    try:
        import mido
    except ImportError as e:
        raise RuntimeError("midi extra missing: pip install -e '.[midi]'") from e
    return mido


def list_ports() -> dict:
    mido = _mido()
    return {"outputs": mido.get_output_names(), "inputs": mido.get_input_names()}


def _bridge_base():
    from pathlib import Path

    from reaper_connector.doctor import default_resource_path

    return default_resource_path() / "AgentBridge"


def serve_alive(max_age_s: float = 6.0) -> bool:
    import time as _time

    hb = _bridge_base() / "log" / SERVE_HEARTBEAT
    try:
        return _time.time() - hb.stat().st_mtime < max_age_s
    except OSError:
        return False


def enqueue_phrase(notes: list[dict], tempo: float = 120.0, timeout: float = 60.0) -> dict:
    """Hand a phrase to the running midi-serve daemon; wait for its receipt."""
    import json as _json
    import time as _time
    import uuid as _uuid

    base = _bridge_base()
    in_d, out_d = base / QUEUE_IN, base / QUEUE_OUT
    if not in_d.is_dir():
        raise RuntimeError("midi queue missing — run `doctor --fix`")
    if not serve_alive():
        raise RuntimeError("no midi-serve daemon (start one: `midi-serve --detach`)")
    jid = _uuid.uuid4().hex[:12]
    (in_d / f"{jid}.json").write_text(_json.dumps({"id": jid, "notes": notes, "tempo": tempo}))
    deadline = _time.time() + timeout
    while True:
        rep = out_d / f"{jid}.json"
        if rep.is_file():
            try:
                receipt = _json.loads(rep.read_text())
            except ValueError:
                pass
            else:
                try:
                    (in_d / f"{jid}.json").unlink(missing_ok=True)
                    rep.unlink(missing_ok=True)
                except OSError:
                    pass
                return receipt
        if _time.time() > deadline:
            raise RuntimeError(f"midi-serve receipt timeout ({jid})")
        _time.sleep(0.05)


def serve_forever() -> None:
    """Hold the virtual port; play every queued phrase in arrival order."""
    import json as _json
    import time as _time

    base = _bridge_base()
    in_d, out_d, log_d = base / QUEUE_IN, base / QUEUE_OUT, base / "log"
    for d in (in_d, out_d, log_d):
        d.mkdir(parents=True, exist_ok=True)
    hb = log_d / SERVE_HEARTBEAT
    last_beat = 0.0
    with PlayerOut() as out:
        while True:
            now = _time.time()
            if now - last_beat >= HEARTBEAT_EVERY_S:
                last_beat = now
                hb.write_text(str(int(now)) + "\n")
            jobs = sorted(in_d.glob("*.json"))
            if not jobs:
                _time.sleep(0.05)
                continue
            job = jobs[0]
            try:
                payload = _json.loads(job.read_text())
            except (OSError, ValueError):
                _time.sleep(0.05)
                continue
            t0 = _time.time()
            try:
                played = out.phrase(payload["notes"], tempo=float(payload.get("tempo", 120)))
                receipt = {"ok": True, "id": payload.get("id"), **played,
                           "secs": round(_time.time() - t0, 2)}
            except (KeyError, TypeError, ValueError) as e:
                receipt = {"ok": False, "id": payload.get("id"), "error": str(e)}
            try:
                (out_d / job.name).write_text(_json.dumps(receipt))
                job.unlink(missing_ok=True)
            except OSError:
                pass


class PlayerOut:
    """Virtual-port MIDI out. Use as context manager to hold the port open."""

    def __init__(self, name: str = PORT_NAME):
        self.name = name
        self._port = None

    def __enter__(self) -> "PlayerOut":
        self._port = _mido().open_output(self.name, virtual=True)
        return self

    def __exit__(self, *exc) -> None:
        if self._port is not None:
            self._port.close()
            self._port = None

    def note(self, pitch: int, vel: int = 96, dur_s: float = 0.5, chan: int = 0) -> dict:
        if self._port is None:
            raise RuntimeError("port not open — use `with PlayerOut():`")
        mido = _mido()
        self._port.send(mido.Message("note_on", note=pitch, velocity=vel, channel=chan))
        time.sleep(max(0.0, dur_s))
        self._port.send(mido.Message("note_off", note=pitch, velocity=0, channel=chan))
        return {"pitch": pitch, "vel": vel, "dur_s": dur_s}

    def phrase(self, notes: list[dict], tempo: float = 120) -> dict:
        """notes: bridge/RPP shape (start_beats/dur_beats). Beats → sleeps."""
        if self._port is None:
            raise RuntimeError("port not open — use `with PlayerOut():`")
        beat = 60.0 / tempo
        cursor = 0.0
        for n in sorted(notes, key=lambda n: n["start_beats"]):
            at = n["start_beats"] * beat
            if at > cursor:
                time.sleep(at - cursor)
                cursor = at
            self._port.send(
                _mido().Message(
                    "note_on", note=n["pitch"], velocity=n.get("vel", 96), channel=n.get("chan", 0)
                )
            )
            off_at = (n["start_beats"] + n["dur_beats"]) * beat
            # naive: note_off scheduled inline only for non-overlapping lines;
            # overlapping parts need the chord-aware path (t7). Sleep to end.
            if off_at > cursor:
                time.sleep(off_at - cursor)
                cursor = off_at
            self._port.send(
                _mido().Message("note_off", note=n["pitch"], velocity=0, channel=n.get("chan", 0))
            )
        return {"notes": len(notes), "tempo": tempo}
