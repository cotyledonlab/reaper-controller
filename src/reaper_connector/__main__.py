"""`reaper-connector` CLI — t1: doctor, bridge-send, status; t2: create, read, render, analyze."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from reaper_connector import bridge as _bridge
from reaper_connector import doctor as _doctor


def cmd_doctor(args: argparse.Namespace) -> int:
    if args.fix:
        result = _doctor.fix()
        print(json.dumps(result, indent=2))
        print("---")
    rep = _doctor.report()
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        lines = [
            f"binary:    {rep['binary']} {'OK' if rep['binary_present'] else 'MISSING'}",
            f"version:   {rep['version']}",
            f"resource:  {rep['resource_path']} {'OK' if rep['resource_present'] else 'MISSING'}",
            f"eval-nag:  {'yes' if rep['eval_nag_key'] else 'no/unknown'}",
            "osc:       "
            + ", ".join(f"{k}={'OK' if v else 'MISSING'}" for k, v in rep["osc_files"].items()),
            "render:    "
            + ", ".join(f"{k}={'OK' if v else 'MISSING'}" for k, v in rep["render_flags"].items()),
            "ports:     " + ", ".join(f"{k}={v}" for k, v in rep["ports"].items()),
            f"bridge:    dirs={rep['bridge']['dirs']} daemon_hint={rep['bridge']['daemon_hint']} "
            f"orphans={rep['bridge']['stale_orphans']}",
            f"overall:   {'OK' if rep['ok'] else 'NOT READY'}",
        ]
        print("\n".join(lines))
        if not rep["ok"]:
            print("hint: run `reaper-connector doctor --fix` for bridge dirs", file=sys.stderr)
    return 0 if rep["ok"] else 1


def cmd_bridge_send(args: argparse.Namespace) -> int:
    try:
        params = json.loads(args.params) if args.params else {}
    except ValueError as e:
        print(f"bad --params JSON: {e}", file=sys.stderr)
        return 2
    try:
        reply = _bridge.send(args.op, params, timeout=args.timeout)
    except _bridge.BridgeTimeout as e:
        print(f"timeout: {e}", file=sys.stderr)
        print("hint: is REAPER running with the agent_bridge.lua startup daemon?", file=sys.stderr)
        return 1
    except _bridge.BridgeError as e:
        print(f"bridge error {e.code}: {e.detail}", file=sys.stderr)
        return 1
    print(json.dumps(reply, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    rep = _doctor.report()
    print(
        json.dumps(
            {
                "version": rep["version"],
                "binary_present": rep["binary_present"],
                "resource_present": rep["resource_present"],
                "daemon_hint": rep["bridge"]["daemon_hint"],
                "heartbeat_age_s": rep["bridge"]["heartbeat_age_s"],
                "ports": rep["ports"],
            },
            indent=2,
        )
    )
    return 0


def _load_params(text: str) -> dict:
    try:
        obj = json.loads(text) if text else {}
    except ValueError as e:
        print(f"bad --params JSON: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(obj, dict):
        print("--params must be a JSON object", file=sys.stderr)
        raise SystemExit(2)
    return obj


def cmd_templates(args: argparse.Namespace) -> int:
    from reaper_connector import templates as _t

    print(json.dumps(_t.list_templates(), indent=2))
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    from reaper_connector import rpp as _rpp
    from reaper_connector import templates as _t

    if args.template not in _t.TEMPLATES:
        print(f"unknown template: {args.template} (have: {list(_t.TEMPLATES)})", file=sys.stderr)
        return 2
    params = _load_params(args.params)
    if "notes" not in params:
        params["notes"] = _t.default_notes()
    try:
        summary = _rpp.create(args.path, **params)
    except (ValueError, RuntimeError) as e:
        print(f"create failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    from reaper_connector import rpp as _rpp

    try:
        info = _rpp.read(args.path)
    except OSError as e:
        print(f"read failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(info, indent=2))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from reaper_connector import audio as _audio

    try:
        result = _audio.render_project(args.path, wav=args.wav, timeout=args.timeout)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
        print(f"render failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def _osc_port(env: str, default: int) -> int:
    try:
        return int(os.environ.get(env, default))
    except ValueError:
        return default


def cmd_osc_send(args: argparse.Namespace) -> int:
    from reaper_connector import osc as _osc

    values: list = []
    for tok in args.values:
        try:
            values.append(json.loads(tok))
        except ValueError:
            values.append(tok)
    try:
        result = _osc.OscClient(host=args.host, port=args.port).send(args.address, values)
    except ValueError as e:
        print(f"osc-send failed: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"osc-send failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


def cmd_telemetry(args: argparse.Namespace) -> int:
    from reaper_connector import osc as _osc

    filt = args.filter.split(",") if args.filter else None
    try:
        events = _osc.capture(port=args.port, secs=args.secs, addresses=filt)
    except RuntimeError as e:
        print(f"telemetry failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"events": events, "count": len(events)}, indent=2))
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    from reaper_connector import music as _music

    try:
        notes = _music.compose_part(_load_params(args.spec))
    except (ValueError, TypeError) as e:
        print(f"compose failed: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"notes": notes, "count": len(notes)}, indent=2))
    return 0


def cmd_midi_ports(args: argparse.Namespace) -> int:
    from reaper_connector import midi as _midi

    try:
        print(json.dumps(_midi.list_ports(), indent=2))
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_midi_hold(args: argparse.Namespace) -> int:
    import time as _time

    from reaper_connector import midi as _midi

    try:
        with _midi.PlayerOut():
            print(f"virtual port '{_midi.PORT_NAME}' open for {args.secs}s", flush=True)
            _time.sleep(args.secs)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_midi_send(args: argparse.Namespace) -> int:
    from reaper_connector import midi as _midi
    from reaper_connector import music as _music

    try:
        if args.what == "note":
            with _midi.PlayerOut() as out:
                result = out.note(args.note, vel=args.vel, dur_s=args.dur)
        else:
            try:
                spec = json.loads(args.spec) if args.spec else {}
            except ValueError as e:
                print(f"bad --spec JSON: {e}", file=sys.stderr)
                return 2
            notes = spec if isinstance(spec, list) else _music.compose_part(spec)
            try:
                result = _midi.enqueue_phrase(notes, tempo=args.tempo)
            except RuntimeError as e:
                if "no midi-serve daemon" not in str(e):
                    raise
                print("warn: no midi-serve daemon — transient port (input mapping won't match)",
                      file=sys.stderr)
                with _midi.PlayerOut() as out:
                    result = out.phrase(notes, tempo=args.tempo)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


def cmd_midi_serve(args: argparse.Namespace) -> int:
    import subprocess as _sp

    from reaper_connector import midi as _midi

    if args.detach:
        log = open("/tmp/reaper-midi-serve.log", "ab")
        _sp.Popen([sys.executable, "-m", "reaper_connector", "midi-serve"],
                  start_new_session=True, stdout=log, stderr=log,
                  cwd=os.path.expanduser("~"))
        print("midi-serve detached (log: /tmp/reaper-midi-serve.log)")
        return 0
    try:
        _midi.serve_forever()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    from reaper_connector import audio as _audio

    try:
        verdict = _audio.analyze_wav(args.wav)
    except (OSError, ValueError) as e:
        print(f"analyze failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reaper-connector", description="Agentic connector for REAPER DAW")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="readiness probe (never launches the GUI)")
    d.add_argument("--fix", action="store_true", help="create AgentBridge/{in,out,log} dirs")
    d.add_argument("--json", action="store_true", help="machine-readable output")
    d.set_defaults(func=cmd_doctor)

    b = sub.add_parser("bridge-send", help="file-drop RPC op through the live daemon")
    b.add_argument("op", help="op name, e.g. ping, hello")
    b.add_argument("--params", default="", help="JSON params object")
    b.add_argument("--timeout", type=float, default=10.0)
    b.set_defaults(func=cmd_bridge_send)

    s = sub.add_parser("status", help="REAPER + bridge detection snapshot")
    s.set_defaults(func=cmd_status)

    t = sub.add_parser("templates", help="list song templates")
    t.set_defaults(func=cmd_templates)

    c = sub.add_parser("create", help="generate an RPP from a template")
    c.add_argument("path", help="output .RPP path")
    c.add_argument("--template", default="song")
    c.add_argument("--params", default="", help='JSON overrides, e.g. {"tempo": 100}')
    c.set_defaults(func=cmd_create)

    r = sub.add_parser("read", help="parse an RPP (tracks, items, notes, fx)")
    r.add_argument("path", help=".RPP path")
    r.set_defaults(func=cmd_read)

    n = sub.add_parser("render", help="headless -renderproject bounce")
    n.add_argument("path", help=".RPP path")
    n.add_argument("--wav", default=None, help="override render output (source RPP untouched)")
    n.add_argument("--timeout", type=float, default=180.0)
    n.set_defaults(func=cmd_render)

    a = sub.add_parser("analyze", help="WAV verdict (audible? clipped? DC?)")
    a.add_argument("wav", help=".wav path")
    a.set_defaults(func=cmd_analyze)

    o = sub.add_parser("osc-send", help="one OSC message to REAPER")
    o.add_argument("address", help="e.g. /play, /track/1/volume")
    o.add_argument("values", nargs="*", help="JSON-parsed args (numbers stay numbers)")
    o.add_argument("--host", default="127.0.0.1")
    o.add_argument("--port", type=int, default=_osc_port("REAPER_OSC_RX", 8000))
    o.set_defaults(func=cmd_osc_send)

    k = sub.add_parser("compose", help="deterministic part builder (notes JSON)")
    k.add_argument("--spec", default='{"shape":"progression"}', help='e.g. {"shape":"chord","root":"C4","quality":"maj7"}')
    k.set_defaults(func=cmd_compose)

    q = sub.add_parser("midi-ports", help="list CoreMIDI ports")
    q.set_defaults(func=cmd_midi_ports)

    h = sub.add_parser("midi-hold", help="hold the virtual out port open for setup")
    h.add_argument("--secs", type=float, default=60.0)
    h.set_defaults(func=cmd_midi_hold)

    v = sub.add_parser("midi-serve", help="persistent phrase player (one port identity)")
    v.add_argument("--detach", action="store_true")
    v.set_defaults(func=cmd_midi_serve)

    d = sub.add_parser("midi-send", help="play notes live into the armed track")
    d.add_argument("what", choices=["note", "phrase"])
    d.add_argument("--note", type=int, default=60)
    d.add_argument("--vel", type=int, default=96)
    d.add_argument("--dur", type=float, default=0.5)
    d.add_argument("--spec", default="", help="phrase notes list or compose spec JSON")
    d.add_argument("--tempo", type=float, default=120.0)
    d.set_defaults(func=cmd_midi_send)

    m = sub.add_parser("telemetry", help="listen for OSC feedback from REAPER")
    m.add_argument("--secs", type=float, default=3.0)
    m.add_argument("--port", type=int, default=_osc_port("REAPER_OSC_TX", 9000))
    m.add_argument("--filter", default="", help="comma-separated addresses, e.g. /time/str,/track/1/vu")
    m.set_defaults(func=cmd_telemetry)
    return p


def cli_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(cli_main())
