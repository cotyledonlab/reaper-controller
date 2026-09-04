# 0001 — scaffold + doctor + file-drop ping/hello

Status: Complete (2026-09-03, live vs REAPER 7.79/macOS-arm64).

Live evidence: `bridge-send ping` → `{"ok": true, "result": {"pong": true}, "adapter": "reascript-lua"}`; `bridge-send hello` → `app_version 7.79/macOS-arm64, tracks 0, state_change_count 2`; `status` → `daemon_hint alive, heartbeat_age_s ~3.5`. No focus stolen, no popups.
Depends on: SPEC.md v0.2 §3–§5.

## Scope

- Python package skeleton (`pyproject`, `src/reaper_connector/`): `doctor`, `bridge` (file-drop JSON-RPC client), CLI (`doctor`, `bridge-send`, `status`). Stdlib only.
- Lua daemon `bridge/agent_bridge.lua`: defer-loop file scanner, ops `ping` + `hello`, atomic replies, heartbeat, never-die `pcall` wrapping.
- Tests: `tests/test_doctor.py` (live install), `tests/test_bridge.py` (fake responder, no DAW).

## Acceptance

1. `python -m pytest` green on John's Mac.
2. `reaper-connector doctor` reports `overall: OK` (7.79, resource dir, OSC ×3, `-renderproject` verified via byte-scan, ports listed).
3. `reaper-connector doctor --fix` creates `AgentBridge/{in,out,log}`.
4. Live: REAPER running + `agent_bridge.lua` loaded via Action list → `reaper-connector bridge-send ping` answers `pong` ≤10 s; `bridge-send hello` returns app version + track count. No focus stolen, no popups.
5. Kill REAPER → `bridge-send ping --timeout 2` exits 1 with daemon hint (timeout path, no traceback).

## Manual daemon install (until t2 automates it)

1. `cp bridge/agent_bridge.lua ~/Library/Application\ Support/REAPER/Scripts/agent_bridge.lua`
2. REAPER → Actions → Show action list → New action… → Load ReaScript → pick it → Run.
3. Optional persistence: SWS Extensions → Startup actions → set as global startup action.
4. `reaper-connector status` should flip `daemon_hint` to `alive` within ~6 s.

## Notes / gotchas

- Never probe with `REAPER --help` — it opens the GUI and hangs the caller. Version comes from `Info.plist`, flags from a `strings`-style byte scan.
- ReaScript Lua has no sockets — hence file-drop, not TCP (§2). TCP is a later transport swap only.
- `hello` avoids `GetProjectName` (binding signature varies); uses `CountTracks` + `GetProjectStateChangeCount`, which are stable.
