# reaper-controller — Specification (v0.2, bridge-first)

Status: v0.3 — tickets 0001–0007 built (Agent Plugin pivot in t7 recorded above). Bridge daemon inside REAPER, not a Pd-clone.
Owner intent: agent as **personal studio engineer + session player** for REAPER.
Constraint: **open background protocols first** — files + OSC + MIDI + HTTP + ReaScript. **No computer-use** (no Accessibility, keystrokes, mouse, screen-scraping).

Eval state (verified 2026-09-03, no GUI launch): REAPER **7.79** at `/Applications/REAPER.app`, resource dir `~/Library/Application Support/REAPER/` (fresh eval `reaper.ini`, `OSC/` ×3, `Scripts/` stub-only), `-renderproject filename.rpp : render project and exit` + `-batchconvert` **verified via `strings`** in the shipping binary, bridge/OSC/web ports free.

## 1. Product statement

`reaper-controller` drives a running REAPER session through a **Lua bridge daemon living inside REAPER**, plus native OSC for high-rate control and files for bulk work:

```
agent --file AgentBridge/in/<op>.json--> agent_bridge.lua (defer loop) -> ReaScript API -> AgentBridge/out/<op>.json
agent --OSC /track/1/volume-------------> REAPER core (Agent.ReaperOSC) -> track vol (+ feedback)
agent --HTTP /_/ACTION/*----------------> stock Web Remote (gaps OSC can't reach)
agent --file session.RPP----------------> REAPER (whole sessions, FX chains, MIDI items)
agent <--file out.wav------------------- REAPER -renderproject (offline bounce, analyzed)
```

Two personas, one bridge — method groups, not transports:
1. **Engineer** (`engineer.*`) — tracks/instruments/FX, routing/sends/folders, levels, monitoring, templates.
2. **Session player** (`player.*`) — write/audition/humanize/quantize MIDI, takes; live play-in over loop.
Plus `project.*` (open/save/identity) and `render.*` (bounce + analyze verdict).

## 2. Why not the Pd hub

Pd's hub works because a patch is flat: fire-and-forget `/freq`, periodic `/level`, done. A DAW is hierarchical and stateful — project > tracks > items/takes > notes > FX > params > envelopes > markers — everything carries identity (GUIDs), and the agent needs **request→reply with errors, discovery, and bulk MIDI**. OSC-alone can't do that (no replies, no lists, bank-sprawl addressing). So:

| Lane | Job | Why |
|---|---|---|
| **Bridge file-drop JSON-RPC** (primary) | all semantic ops: engineer/player/project | structured replies + errors + GUIDs; zero extensions, zero sockets (ReaScript Lua has no socket lib — file-drop sidesteps it), debuggable on disk |
| **OSC** (secondary, high-rate) | transport, vol/pan/mute/solo, tempo, jog, peak feedback | native, background, sub-ms; narrowed `Agent.ReaperOSC`, not Default sprawl |
| **Web Remote HTTP** (gap-filler) | action IDs, state chunks OSC lacks | stock server, localhost-only, no custom code |
| **Files** (bulk/offline) | `.RPP` generation, `.mid` parts, `-renderproject` bounce | whole-session authoring + deterministic verify loop |
| **MIDI ports** (live only) | play-in monitoring alongside the human | bridge-inserted MIDI covers writing; IAC kept only for live jamming |

TCP/UNIX-socket RPC is a *later* upgrade (needs `js_ReaScriptAPI`/SWS socket help) — and it changes no tool surface, only the bridge transport.

## 3. Architecture

```
                ┌────────────── agent harness ──────────────┐
                │ Skill / MCP tools / CLI / pi tools        │
                └──────┬────────┬────────┬────────┬─────────┘
                       │ files  │ OSC    │ HTTP   │ files
                ┌──────▼────────▼────────▼────────▼─────────┐
                │ reaper-connector (Python, stdlib-first)   │
                │ bridge.py  osc.py  web.py  rpp.py         │
                │ midi.py  audio.py  manager.py(doctor)     │
                └──────┬────────┬────────┬────────┬─────────┘
                       │ JSON   │ OSC    │ HTTP   │ RPP/WAV
                ┌──────▼────────▼────────▼────────▼─────────┐
                │ REAPER 7.x (GUI open, background)         │
                │ agent_bridge.lua (startup daemon)         │
                │ Agent.ReaperOSC + agent_hub.RPP           │
                └──────────────────────────────────────────┘
```

### 3.1 Bridge protocol (file-drop JSON-RPC v1)

- Dirs: `<ResourcePath>/AgentBridge/{in,out,log}/` (created by `doctor --fix`).
- Request: `in/<op_id>.json` — `{"v":1,"op":"engineer.add_fx","op_id":"<uuid>","params":{...}}`.
- Reply: `out/<op_id>.json` — `{"v":1,"op_id":"...","ok":true,"result":{...},"adapter":"reascript-lua","evidence":[...]}` or `{"ok":false,"error":{"code":"...","detail":"..."}}`.
- Daemon: `agent_bridge.lua` startup action, `reaper.defer` loop ~10 Hz, scans `in/`, executes against ReaScript API, writes `out/`, prunes after host ACKs (host deletes request after reading reply; daemon skips IDs already answered).
- Host client `bridge.py`: `send(op, params, timeout=10)` → writes request, polls `out/`, returns parsed reply or raises `BridgeTimeout`; stale-file hygiene (`doctor` flags orphans >1 h).
- JSON: Python stdlib `json` on host; Lua side vendors a small pure-Lua JSON module (`bridge/lib/json.lua`) — no externals.

### 3.2 Module map (stdlib-first, no native build)

| Module | Job |
|---|---|
| `bridge.py` | file-drop RPC client (`send`, `wait`, op helpers `ping/hello`) |
| `doctor.py` | readiness: binary, version, resource paths, OSC files, render flags, ports, bridge dirs/daemon |
| `osc.py` | (t2+) live control + feedback client; ships `Agent.ReaperOSC` |
| `web.py` | (t2+) Web Remote HTTP client for gap actions |
| `rpp.py`/`templates.py` | (t2+) text-`.RPP` builder/reader: tracks, MIDI items, FX chains, sends |
| `midi.py` | (t3+) live play-in over IAC/virtual port; file parts earlier via `rpp.py` |
| `audio.py` | (t2+) ported `analyze_wav` verdicts (audible? clipped? DC?) + render orchestration |
| `manager.py` | (t2+) `launch/stop/status` process ownership (doctor owns detection in t1) |

## 4. Interfaces

```bash
reaper-connector doctor [--fix]              # install/version/paths/OSC/render-flags/ports/bridge dirs
reaper-connector bridge-send ping            # file-drop round-trip through live REAPER (t1: ping/hello)
reaper-connector status                      # REAPER running? bridge alive? (t1: detection only)
# t2+: templates | create | read | launch | osc-send | telemetry | render | analyze | web | midi-send | stop
```

MCP tools mirror CLI 1:1 (`reaper_doctor`, `reaper_bridge_send`, …). Skill `skills/reaper/SKILL.md` holds safety path + engineer/player recipes. pi `reaper_*` tools shell out to CLI (same pattern as `pd_*`).

## 5. Capability coverage (slices)

| # | Slice | Verify (real REAPER 7.79, John's Mac) |
|---|---|---|
| t1 | scaffold + `doctor` + file-drop `ping/hello` vs live daemon | `doctor` clean; `bridge-send ping` → `pong` ≤10 s; no GUI focus stolen |
| t2 | RPP builder/reader + `create/read` + `-renderproject` + `analyze` | one-ReaSynth RPP renders audible (`analyze ok=true`) — the afternoon loop |
| t3 | OSC lane: `Agent.ReaperOSC` + transport/vol/tempo + `/level` telemetry | play/stop with feedback; level delta on vol change |
| t4 | bridge depth: `engineer.add_fx/set_param`, `player.insert_midi/quantize` | FX list + note list observed back, not just requested |
| t5 | routing/sends/folders/markers/loop + `web` gap coverage | `read` shows sends; loop renders correct length |
| t6 | player: humanize/chords/strums + IAC play-in + takes | rendered riff audible + humanized velocity spread observed |
| t7 | Agent Plugin package (plugin.json + skills/ + mcp.json, agent-plugins.org v1.0.0) + FastMCP server + conformance tests | live MCP handshake via plugin launcher (14 tools, status answers); skill matches pi loader rules |

Deferred v1: comping UI, notation, video, ReaRoute-ASIO (Win-only), ARA, full envelope lanes (RPP write is stretch).

## 6. RPP scope (t2)

Builder supports tempo/map, tracks (vol/pan/mute/solo, folder depth, rec-arm + MIDI input), `<ITEM>` + `<SOURCE MIDI>` (int ticks, vel, channel), `<FXCHAIN>` (ReaSynth + named VST/AU passthrough, opaque chunks flagged `inferred`), `<SEND>` routing. Unknown chunks round-trip opaquely with `read` warnings (same philosophy as Pd `validate()`).

## 7. Safety

- **Disposable projects**: agent mutation only under `~/Music/ReaperConnector/Test Projects/` (or repo `scratch/`); fixtures copied, never opened in place.
- **Gates**: `doctor/read/analyze/telemetry` always allowed; `bridge-send` reversible ops default; arbitrary-Lua upload, overwrite/delete outside test dir, touching user projects = confirmed-risk (explicit confirm + project-path identity check).
- **Hygiene**: master limiter in every template; stale `in/*.json` orphans flagged by `doctor`; `stop --all` (t2+) owns REAPER/ports/scratch cleanup.
- **Evidence**: every reply carries `{adapter, requested vs observed/inferred, evidence}` — requested is never presented as observed (Logic SPEC §8 rule, kept).

## 8. Verification

- Unit (no DAW): RPP round-trip, bridge client vs fake responder, `analyze` verdicts — `pytest`.
- Contract: server tool inventory + live handshake probe (t7; replaces CLI↔MCP parity — same coverage, real wire).
- Real-REAPER acceptance per slice on John's Mac; a capability is `supported` only after its gate passes. Every live gotcha → `docs/pitfalls.md` entry (Pd proved this pays).
- Red→green per ticket, docs + clear commit before the next slice.

## 9. Open questions (carried)

1. VSTi/AU day-one set (ReaSynth + ? Surge/Vital assumed free).
2. Player priority: audition (write→render) vs live loop-jam with you — both planned, order TBD.
3. `reaper_*` native in pi vs MCP-only — answered in t7: neither; portable Agent Plugin package, pi adopts via skill-dir + MCP registration (no pi namespaces guessed).
4. TCP upgrade trigger: only if file-drop latency (~100 ms) blocks a real workflow.

*Built: tickets 0001–0007 complete (2026-09-04). Next work extends from here — see newest ticket + `docs/pitfalls.md` last entries.*
