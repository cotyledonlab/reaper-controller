"""File-drop JSON-RPC client for the in-REAPER Lua bridge daemon.

Protocol v1 (see SPEC.md §3.1):
  request: <ResourcePath>/AgentBridge/in/<op_id>.json
    {"v": 1, "op": "ping", "op_id": "<uuid>", "params": {...}}
  reply:   <ResourcePath>/AgentBridge/out/<op_id>.json
    {"v": 1, "op_id": "...", "ok": true, "result": {...},
     "adapter": "reascript-lua", "evidence": [...]}
    or {"v": 1, "op_id": "...", "ok": false,
        "error": {"code": "...", "detail": "..."}}

No sockets (ReaScript Lua has none) — plain files the daemon's defer loop
scans. Stdlib only.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from reaper_connector.doctor import default_resource_path

PROTOCOL_V = 1
POLL_INTERVAL_S = 0.05


class BridgeTimeout(RuntimeError):
    pass


class BridgeError(RuntimeError):
    """Daemon answered ok=false."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def bridge_dirs(resource_path: Path | None = None) -> dict[str, Path]:
    base = (resource_path or default_resource_path()) / "AgentBridge"
    return {"base": base, "in": base / "in", "out": base / "out", "log": base / "log"}


def send(
    op: str,
    params: dict | None = None,
    timeout: float = 10.0,
    op_id: str | None = None,
    resource_path: Path | None = None,
    cleanup: bool = True,
) -> dict:
    """Write a request, poll for the reply, return the parsed reply dict.

    Raises BridgeTimeout (no reply in time) or BridgeError (ok=false).
    With cleanup=True (default) removes the request file after reading the
    reply, plus the reply file — orphans older than 1 h are flagged by doctor.
    """
    dirs = bridge_dirs(resource_path)
    if not dirs["in"].is_dir() or not dirs["out"].is_dir():
        raise FileNotFoundError(
            f"AgentBridge dirs missing under {dirs['base']} — run `reaper-connector doctor --fix`"
        )
    oid = op_id or uuid.uuid4().hex[:12]
    req_path = dirs["in"] / f"{oid}.json"
    rep_path = dirs["out"] / f"{oid}.json"
    req_path.write_text(
        json.dumps({"v": PROTOCOL_V, "op": op, "op_id": oid, "params": params or {}})
    )
    deadline = time.time() + timeout
    try:
        while True:
            if rep_path.is_file():
                try:
                    reply = json.loads(rep_path.read_text())
                except (OSError, ValueError):
                    pass  # half-written; keep polling
                else:
                    if reply.get("ok") is False:
                        err = reply.get("error", {})
                        raise BridgeError(
                            str(err.get("code", "UNKNOWN")),
                            str(err.get("detail", "")),
                        )
                    return reply
            if time.time() > deadline:
                raise BridgeTimeout(f"no reply for op '{op}' ({oid}) in {timeout}s")
            time.sleep(POLL_INTERVAL_S)
    finally:
        if cleanup:
            for p in (req_path, rep_path):
                try:
                    p.unlink()
                except OSError:
                    pass
