"""Readiness probe for REAPER + reaper-connector. Stdlib only, never launches the GUI.

Checks (all observation, no mutation unless fix=True):
  binary present + version (Info.plist, no `--help` launch — that opens the GUI)
  resource dir (~/Library/Application Support/REAPER on macOS)
  eval state (reaper.ini [nag] key)
  OSC pattern files present
  -renderproject / -batchconvert flags verified via `strings`-style byte scan
  OSC (8000/9000) + Web (8080) ports free-or-used report
  AgentBridge/{in,out,log} dirs (+ heartbeat freshness = daemon alive hint)
"""

from __future__ import annotations

import os
import plistlib
import socket
import time
from pathlib import Path

APP_PATH = Path("/Applications/REAPER.app")
BIN_PATH = APP_PATH / "Contents/MacOS/REAPER"
PLIST_PATH = APP_PATH / "Contents/Info.plist"

OSC_FILES = ("Default.ReaperOSC", "LogicTouch.ReaperOSC", "LogicPad.ReaperOSC")
BRIDGE_SUBDIRS = ("in", "out", "log")

# Ports we care about. The file-drop bridge needs no port; OSC/Web do.
WATCH_PORTS = {"osc_rx": 8000, "osc_feedback": 9000, "web_remote": 8080}


def default_resource_path() -> Path:
    override = os.environ.get("REAPER_RESOURCE_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library/Application Support/REAPER"


def _app_version() -> str | None:
    try:
        with open(PLIST_PATH, "rb") as f:
            pl = plistlib.load(f)
        return str(pl.get("CFBundleShortVersionString"))
    except OSError:
        return None


def _binary_has_flag_candidates() -> dict[str, bool]:
    """Byte-scan the binary for CLI flags. 26 MB — read in chunks, no exec."""
    found = {"renderproject": False, "batchconvert": False}
    try:
        with open(BIN_PATH, "rb") as f:
            tail = b""
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                buf = tail + chunk
                if b"-renderproject" in buf:
                    found["renderproject"] = True
                if b"-batchconvert" in buf:
                    found["batchconvert"] = True
                if all(found.values()):
                    break
                tail = buf[-64:]
    except OSError:
        pass
    return found


def _port_state(port: int) -> str:
    """free = bindable; used = something already listens (REAPER or other)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return "free"
    except OSError:
        return "used"
    finally:
        s.close()


def _bridge_state(res: Path) -> dict:
    base = res / "AgentBridge"
    dirs = {name: (base / name).is_dir() for name in BRIDGE_SUBDIRS}
    hb = base / "log" / "heartbeat.txt"
    heartbeat_age_s: float | None = None
    if hb.is_file():
        try:
            heartbeat_age_s = time.time() - hb.stat().st_mtime
        except OSError:
            heartbeat_age_s = None
    orphans = 0
    in_dir = base / "in"
    if in_dir.is_dir():
        try:
            now = time.time()
            for p in in_dir.glob("*.json"):
                try:
                    if now - p.stat().st_mtime > 3600:
                        orphans += 1
                except OSError:
                    continue
        except OSError:
            pass
    return {
        "dirs": dirs,
        "heartbeat_age_s": heartbeat_age_s,
        "daemon_hint": (
            "alive"
            if heartbeat_age_s is not None and heartbeat_age_s < 15
            else ("stale" if heartbeat_age_s is not None else "unknown")
        ),
        "stale_orphans": orphans,
    }


def osc_device_configured(res: Path) -> dict:
    """True iff reaper.ini names an OSC control surface `Agent` (ticket 0003).

    Persists as e.g. csurf_0=OSC "Agent" 3 8000 "127.0.0.1" 9000 1024 10 "Agent".
    Informational only — never gates overall ok (fresh installs lack it)."""
    try:
        text = (res / "reaper.ini").read_text(errors="replace")
    except OSError:
        return {"configured": False, "line": None}
    for ln in text.splitlines():
        if ln.startswith("csurf_") and ln.rstrip().endswith('"Agent"') and "OSC" in ln:
            return {"configured": True, "line": ln.strip()}
    return {"configured": False, "line": None}


def report() -> dict:
    res = default_resource_path()
    ini = res / "reaper.ini"
    eval_nag = False
    try:
        eval_nag = "[nag]" in ini.read_text(errors="replace")
    except OSError:
        pass
    osc_dir = res / "OSC"
    flags = _binary_has_flag_candidates()
    rep = {
        "binary": str(BIN_PATH),
        "binary_present": BIN_PATH.is_file(),
        "version": _app_version(),
        "resource_path": str(res),
        "resource_present": res.is_dir(),
        "eval_nag_key": eval_nag,
        "scripts_present": (res / "Scripts").is_dir(),
        "osc_files": {name: (osc_dir / name).is_file() for name in OSC_FILES},
        "render_flags": flags,
        "ports": {name: _port_state(p) for name, p in WATCH_PORTS.items()},
        "osc_device": osc_device_configured(res),
        "bridge": _bridge_state(res),
    }
    rep["ok"] = bool(
        rep["binary_present"]
        and rep["resource_present"]
        and flags["renderproject"]
        and all(rep["osc_files"].values())
    )
    return rep


def fix() -> dict:
    """Create AgentBridge/{in,out,log,midi-in,midi-out}. Doctor's only mutation."""
    res = default_resource_path()
    base = res / "AgentBridge"
    created = []
    for name in (*BRIDGE_SUBDIRS, "midi-in", "midi-out"):
        d = base / name
        d.mkdir(parents=True, exist_ok=True)
        created.append(str(d))
    return {"created": created, "bridge": _bridge_state(res)}
