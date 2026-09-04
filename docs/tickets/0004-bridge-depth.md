# 0004 — bridge depth: verifiable mix, FX discovery, quantize/humanize

Status: Complete (2026-09-04, live vs REAPER 7.79/macOS-arm64).

Live evidence: get_mix caught the project at +12 dB (D_VOL 3.98) from
t3's OSC `1.0` send — restored to unity via bridge (observed 1.0). Mute
round-trips. fx_list → ReaSynth/18 params; get/set_param exact
(0.7→0.7, restore→0.0006) after fixing a single-vs-double return bug
(reply carried `observed:nil` as its own evidence). quantize →
`{fixed:0}` on the clean riff. humanize → vel 88–103, re-render
`analyze ok=true` (peak −3.1 dB). doctor `osc_device.configured=true`.
27 pytest green.
Depends on: 0001–0003.

## Scope

1. Lua v3 ops (`bridge/agent_bridge.lua`):
   - `engineer.get_mix {track}` → observed `{volume, pan, mute, solo}`.
   - `engineer.set_volume/pan/mute` → `{requested, observed}` (read-back, never trust the send).
   - `engineer.fx_list {track}` → `[{index, name, params}]` (discovery).
   - `engineer.fx_get_param/fx_set_param {track, fx, param, value}` → observed normalized values.
   - `player.quantize {track, item?, grid_beats=0.25}` → `{notes, fixed, max_dev_beats}`.
   - `player.humanize {track, item?, timing_beats=0.02, vel_amount=6}` → `{notes, vel_min, vel_max}`.
   - Shared `find_take` helper (first MIDI take, or item by `IP_ITEMNUMBER`).
2. `doctor`: `osc_device` field from `reaper.ini` `csurf_N` lines (informational, never gates `ok`).
3. Tests: doctor osc-device parse (tmp ini with/without line); op coverage is live-only (no Lua runtime in CI — noted, accepted).

## Reload (v2 → v3)

v2 has the instance guard but no remote code-reload, so: `bridge-send
bridge.shutdown`, then Actions → run `agent_bridge.lua` again (same file,
already deployed to `Scripts/`). Guard prevents doubles if the old one
lingers — but shutdown first to avoid two daemons racing mutating ops.

## Acceptance (live, reference project, track 0)

1. `get_mix` → `{volume:1.0, pan:0.0, mute:false, solo:false}`.
2. `set_volume 0.5` → observed 0.5; restore 1.0 → observed 1.0.
3. `set_mute true` → observed true; restore false.
4. `fx_list` → ReaSynth index 0 with param count; `fx_get_param 0` reads a
   normalized value; `fx_set_param` round-trips (restore original after).
5. `quantize` on the on-grid riff → `{fixed:0}` (idempotent, proves honesty).
6. `humanize` → vel spread widens in reply evidence; riff still renders
   `analyze ok=true` after (musical, not destructive).
7. `doctor` reports `osc_device.configured=true`; `pytest` green.
