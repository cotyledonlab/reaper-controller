# 0008 — bridge op: `engineer.fx_param_names` (sound design by name)

Status: Complete (2026-09-05, live vs REAPER 7.79/macOS-arm64).

Live evidence: Surge XT → `total=2858` (macros M1–M8 first, then full
Scene A/B tree); Vital → `total=2986` (Envelope/Filter/Osc/Macro
groups). Drove six Surge targets by name (Amp EG Sustain/Decay/Release,
Filter 1 Cutoff/Resonance, Filter EG Decay) and six Vital targets
(Env1 Sustain/Decay/Release, Filter 1 Cutoff/Resonance, Osc1 Unison
Voices) — every set observed back, re-render `analyze ok=true`
(peak −1.1 dB). Motivating case: two init patches sounded cheesy in the
Midnight Driver session; named params fixed them in one pass each.
Depends on: 0004 (extends the fx_get/set_param pair).

## Scope

1. Lua v4 op (`bridge/agent_bridge.lua`):
   - `engineer.fx_param_names {track, fx, from=0, count=total}` →
     `{total, from, names:[{index, name}]}` (chunked — big synths expose
     thousands; `fx_list` already reports the count).
2. No host changes: `bridge-send` / MCP `reaper_bridge_send` pass ops
   through generically.
3. Skill: `skills/reaper/SKILL.md` discovery section gained the
   sound-design loop (names → get → set → re-render).
4. Tests: op coverage is live-only (no Lua runtime in CI — 0004
   precedent, accepted); suite 47 green.

## Reload (v3 → v4)

Daemon is in-memory: deploy means copy to
`~/Library/Application Support/REAPER/Scripts/agent_bridge.lua`, then
reload — REAPER restart (SWS startup action) or `bridge.shutdown` +
re-run (0004 procedure). New op verified only after reload
(`observed:total=2858`).
