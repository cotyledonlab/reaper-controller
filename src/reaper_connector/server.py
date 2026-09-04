"""MCP server: the REAPER studio engineer + session player as agent tools.

Mirrors the CLI core 1:1 (see __main__.py). Long-lived daemons (REAPER +
agent_bridge.lua, midi-serve) stay outside the server; tools are/Borrow
short calls with explicit timeouts.

Run: `reaper-connector-server` (stdio) — or via the plugin launcher
`./bin/reaper-connector-server` from the package root.
"""

from __future__ import annotations


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit(
            "The 'mcp' package is not installed; run `pip install \"reaper-controller[mcp]\"`"
        )

    from reaper_connector import audio as _audio
    from reaper_connector import bridge as _bridge
    from reaper_connector import doctor as _doctor
    from reaper_connector import music as _music
    from reaper_connector import rpp as _rpp
    from reaper_connector import templates as _tmpl

    mcp = FastMCP("reaper")

    @mcp.tool()
    def reaper_doctor(fix: bool = False) -> dict:
        """Readiness probe: binary, version, resource paths, OSC files,
        render flags, ports, OSC device, bridge state. fix=true creates
        AgentBridge dirs. Never launches the GUI."""
        if fix:
            _doctor.fix()
        return _doctor.report()

    @mcp.tool()
    def reaper_status() -> dict:
        """REAPER + bridge daemon detection snapshot."""
        rep = _doctor.report()
        return {
            "version": rep["version"],
            "binary_present": rep["binary_present"],
            "daemon_hint": rep["bridge"]["daemon_hint"],
            "osc_device": rep["osc_device"],
            "ports": rep["ports"],
        }

    @mcp.tool()
    def reaper_bridge_send(op: str, params: dict | None = None, timeout: float = 10.0) -> dict:
        """One file-drop RPC op through the in-REAPER Lua daemon, e.g.
        ping, hello, engineer.get_mix, engineer.add_fx, player.insert_midi.
        Replies carry observed-back evidence; errors raise BridgeError text."""
        try:
            return _bridge.send(op, params or {}, timeout=timeout)
        except (_bridge.BridgeTimeout, _bridge.BridgeError, FileNotFoundError) as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    def reaper_templates() -> dict:
        """Song templates and their defaults."""
        return _tmpl.list_templates()

    @mcp.tool()
    def reaper_create(path: str, params: dict | None = None, template: str = "song") -> dict:
        """Generate a .RPP song file (REAPER-verbatim skeleton + params:
        name, tempo, notes, length_sec). Returns the summary."""
        from reaper_connector import music as _m

        params = dict(params or {})
        if "notes" not in params:
            params["notes"] = _m.default_notes()
        return _rpp.create(path, **params)

    @mcp.tool()
    def reaper_read(path: str) -> dict:
        """Parse an RPP: tempo, tracks (mix, fx, items, take lanes, notes),
        sends, markers, selection. Warnings flag the unknown."""
        return _rpp.read(path)

    @mcp.tool()
    def reaper_render(path: str, wav: str | None = None, timeout: float = 180.0) -> dict:
        """Headless -renderproject bounce (GUI untouched). With wav, renders
        a patched copy — the source RPP is never modified."""
        return _audio.render_project(path, wav=wav, timeout=timeout)

    @mcp.tool()
    def reaper_analyze(wav: str) -> dict:
        """WAV verdict: ok=true means audible, unclipped, no DC offset."""
        return _audio.analyze_wav(wav)

    @mcp.tool()
    def reaper_osc_send(address: str, args: list | None = None) -> dict:
        """One live OSC message, e.g. /play, /track/1/volume [0.5].
        Track numbers are 1-based (OSC convention)."""
        from reaper_connector import osc as _osc

        return _osc.OscClient().send(address, args or [])

    @mcp.tool()
    def reaper_telemetry(secs: float = 3.0, addresses: list | None = None) -> dict:
        """Listen for OSC feedback (timecode, VU, echoes). Returns
        {events, count}. Capture DURING sends — echoes are immediate."""
        from reaper_connector import osc as _osc

        events = _osc.capture(secs=secs, addresses=addresses)
        return {"events": events, "count": len(events)}

    @mcp.tool()
    def reaper_compose(spec: dict) -> dict:
        """Deterministic part builder: {shape: chord|progression|strum|bass,
        ...}. Returns {notes, count} in bridge/RPP note shape."""
        notes = _music.compose_part(spec)
        return {"notes": notes, "count": len(notes)}

    @mcp.tool()
    def reaper_midi_send(notes: list, tempo: float = 120.0, timeout: float = 60.0) -> dict:
        """Play a phrase live into the armed track via the midi-serve
        daemon queue (persistent port identity). Needs midi-serve running."""
        from reaper_connector import midi as _midi

        try:
            return _midi.enqueue_phrase(notes, tempo=tempo, timeout=timeout)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    def reaper_midi_ports() -> dict:
        """CoreMIDI ins/outs visible from here (is the virtual port up?)."""
        from reaper_connector import midi as _midi

        try:
            return _midi.list_ports()
        except RuntimeError as e:
            return {"error": str(e)}

    @mcp.tool()
    def reaper_midi_serve_status() -> dict:
        """Is the persistent phrase player alive? (Lifecycle stays CLI.)"""
        from reaper_connector import midi as _midi

        return {"alive": _midi.serve_alive()}

    mcp.run()


if __name__ == "__main__":
    main()
