---
name: reaper
description: Drive the REAPER DAW as a studio engineer and session player. Use when setting up tracks/instruments/FX, routing, mixing, composing MIDI parts, playing in live, cutting takes, or bouncing and verifying audio — all over background protocols (bridge/OSC/MIDI/files), never computer-use.
---

# REAPER studio connector

You are working a real REAPER 7 session through three lanes. Learn the lanes
once; every persona below rides them.

## First: safety path (do this before improvising)

1. **Pre-flight**: `reaper-connector doctor` (or `reaper_doctor`). Overall OK
   means binary, resource dir, OSC patterns, and `-renderproject` all check
   out. `doctor --fix` creates the bridge/queue dirs — its only mutation.
2. **Daemons**: REAPER must run with `agent_bridge.lua` loaded (action list)
   and `midi-serve` holding the virtual port. `status` / `reaper_status`
   shows both; a dead daemon looks like timeouts, not errors — check status.
3. **Disposable projects**: mutate only test/scratch projects. Reads,
   renders, and telemetry are always safe; arbitrary Lua, overwrites outside
   test dirs, and user projects are confirmed-risk (ask first).
4. **Requested ≠ observed**: every bridge reply carries `observed` evidence.
   Never claim a mix/MIDI state you didn't read back.

## The three lanes

- **Bridge** (`bridge-send` / `reaper_bridge_send`): exact verbs with
  observed-back replies — mix (`engineer.get_mix/set_volume/set_pan/set_mute`,
  `engineer.fx_list/fx_get_param/fx_set_param`), routing (`set_folder`,
  `add_send/list_sends`), markers/loop, MIDI (`player.insert_midi/quantize/
  humanize/rec_arm/select_take`), project (`save/set_render`), input
  (`engineer.get_input`). Bridge track indices are **0-based**.
- **OSC** (`osc-send` / `telemetry`): the live console — `/play /stop
  /record`, `/track/N/volume|pan|mute|solo` (1-based N), `/tempo`
  (normalized 40+256v), `/action <id>` for any REAPER action, `/time/str`
  + `/track/N/vu` telemetry back. Capture DURING sends (echoes are instant).
- **Files** (`create/read/render/analyze`): songs as text `.RPP`, headless
  `-renderproject` bounces (GUI untouched), stdlib WAV verdicts. Render
  paths must be absolute and space-free.

## Engineer recipes

```bash
reaper-connector bridge-send engineer.get_mix --params '{"track":0}'
reaper-connector bridge-send engineer.set_volume --params '{"track":0,"value":0.5}'  # gain units: 1.0 = unity
reaper-connector bridge-send engineer.fx_list --params '{"track":0}'
reaper-connector osc-send /track/1/volume 0.5   # fader taper to +12dB — never for exact unity
```

Summing bus: folder parent must precede children and tracks can't be
reordered — create the MIXBUS track first (or human-drag it to the
top), `add_fx` a flat transparent comp, then `set_folder` depth 1 on
the bus and -1 on the last track; verify via `read` (`ISBUS`) +
render. Full rules: pitfalls #18–21.

## Plugin discovery (read before reaching for ReaSynth)

`docs/plugins.md` (repo) is the observed instrument/FX inventory — every
entry loaded live with its exact `engineer.add_fx` string. Discover
before defaulting: check the inventory, `add_fx` by name, confirm via
the reply's observed `name`, then `render` + `analyze`. ReaSynth is the
fallback, not the first pick — Surge XT is render-verified, Vital /
Dexed / OB-Xd / BBC SO / Splice INSTRUMENT all load.

Sound design: `engineer.fx_param_names` lists a plugin's knobs by index
(chunk with `from`/`count` — big synths expose thousands). Read current
values with `engineer.fx_get_param`, move them with
`engineer.fx_set_param` (normalized 0–1, observed back), then re-render
— every tweak in Midnight Driver (Surge/Vital envelopes, filters,
unison) went through this loop.

## Player recipes

```bash
reaper-connector compose --spec '{"shape":"progression","key":"C4"}'   # notes JSON to stdout
reaper-connector bridge-send player.insert_midi --params '{"track":2,"start_sec":0,"length_sec":8,"notes":[...]}'
reaper-connector midi-send phrase --spec '[{...notes...}]' --tempo 120  # via midi-serve queue
reaper-connector bridge-send player.quantize --params '{"track":2,"grid_beats":0.25}'
```

Punch rule: never start phrases on beat 0 (transport roll-up eats the
downbeat); count in 1–2 beats. After recording, `read` the file — take
lanes show what really landed — then `render` + `analyze` (`ok=true` =
audible, unclipped). Unknown instrument map? Chromatic-sweep it: one
note per 0.5 s across the range, bounce, per-note peak slice — that's
how ReaSynDr was unmasked as a single pitch-tracking voice.

## Gotchas (full list: references/pitfalls.md — bundled copy, also at docs/pitfalls.md in the repo)

- `n/tempo` = 40+256v; `/tempo/str` echoes true BPM on change only.
- `/track/N/volume` sends are NOT echoed — prove mix moves with VU deltas.
- Bridge volume is gain (1.0 = unity); OSC 1.0 = +12 dB fader top.
- Loop points never truncate renders (bounds rule); length via items.
- Sends live on destinations (`AUXRECV`); selected take plays (read lanes!).
- Virtual MIDI ports have identity: one permanent `midi-serve`, re-map +
  re-enable after any endpoint churn. RENDER_FILE must be absolute.
