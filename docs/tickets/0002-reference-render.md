# 0002 — reference build + RPP builder + headless render + analyze

Status: Complete (2026-09-03, live vs REAPER 7.79/macOS-arm64).
Depends on: 0001 (bridge ping/hello live).

## Why this order

Host-side `.RPP` authoring must be grounded in reality, not memory. So: use
the bridge to build a minimal project *inside* running REAPER, save it, read
the bytes REAPER itself wrote — that file becomes the golden reference for
`rpp.py`. No GUI work: all ops go through the file-drop bridge.

## Scope

1. Bridge v2 ops (shipped in `bridge/agent_bridge.lua`, deployed to
   `Scripts/`): `bridge.shutdown`, `engineer.add_track`, `engineer.add_fx`,
   `player.insert_midi`, `project.set_render`, `project.save`.
2. Live reference build in the eval install: 1 track "AgentSynth" + ReaSynth
   + 8-note MIDI item + render path set + save to `scratch/t2-ref.RPP`.
3. `src/reaper_connector/rpp.py` + `templates.py`: emit/parse the reference
   constructs (project header/tempo, track, item, MIDI source, FX chain,
   render file). Unknown chunks round-trip opaquely.
4. `src/reaper_connector/audio.py`: stdlib `analyze_wav` (rms/peak/silence/
   clip/DC verdict, JSON like pd-connector).
5. CLI: `create`, `read`, `render` (`-renderproject`, headless), `analyze`.
6. Tests: builder round-trip (no DAW) + live acceptance below.

## Acceptance

1. Reference `scratch/t2-ref.RPP` built + saved purely via bridge ops.
2. `render scratch/t2-ref.RPP --wav scratch/t2-ref.wav` (headless
   `-renderproject`) exits 0 without touching the open GUI project.
3. `analyze scratch/t2-ref.wav` → `ok=true` (audible, unclipped).
4. `create` emits an RPP that also renders `ok=true` (builder matches reference).
5. `pytest` green.

## Upgrade note (v1 → v2 daemon)

v1 has no single-instance guard and no `bridge.shutdown`, so: **quit REAPER
without saving (project is empty), reopen, Actions → run `agent_bridge.lua`
again.** v2 writes extstate heartbeats; future upgrades can use
`bridge-send bridge.shutdown` instead of restarting.

## Open unknowns

- `RENDER_FILE` project-info key: verified by readback in `project.set_render`
  reply; if readback mismatches, inspect saved RPP for the render-file line.
- Default render format/bounds on fresh eval: read from saved RPP; patch only
  if not WAV/entire-project.
- ReaSynth match name: `engineer.add_fx` errors `FX_NOT_FOUND` with the tried
  name if the match string is wrong — retry with fuller name.
