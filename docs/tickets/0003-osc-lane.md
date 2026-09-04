# 0003 — OSC lane: Agent surface + send + telemetry

Status: Complete (2026-09-03, live vs REAPER 7.79/macOS-arm64).

Live evidence: one-time setup took ~2 min (only correction: Device IP
`0.0.0.0` → `127.0.0.1`). `/play` → `/time/str` + `/beat/str` advance,
`/track/1/vu` + `/master/vu` stream (~10 Hz). Vol 0.2→0.5 VU delta
0.263→0.477 (mix moves are real). `/action 40042` rewind verified via
timecode reset. Tempo mapping cracked: `n/tempo` = 40+256v (0.5→168,
0.3125→120, echoed). Project left as found (vol 1.0, 120 BPM, stopped).
26 pytest green.
Depends on: 0001 (doctor/bridge), 0002 (reference song plays).

## Scope

1. `osc/Agent.ReaperOSC`: 32 fixed tracks (`/track/N/` == REAPER track N,
   no banks), transport, tempo echo, track vol/pan/mute/solo/VU, master,
   `ACTION i/action` gap-filler. Deliberately no FX-param feedback (flood —
   see pattern-file warning; t4 scopes it).
2. `src/reaper_connector/osc.py`: stdlib OSC 1.0 (UDP send + message/bundle
   parse, int/float/str/bool/nil). No python-osc dependency.
3. CLI: `osc-send ADDRESS [values…]` (JSON-parsed args), `telemetry --secs
   [--filter …]` → `{events, count}` JSON. Ports via `REAPER_OSC_RX`
   (default 8000) / `REAPER_OSC_TX` (default 9000).
4. Tests: codec round-trip, trigger-no-args, bundle, loopback, capture —
   no DAW needed.

## One-time setup (human, ~2 min — mirrors Mackie onboarding)

1. `cp osc/Agent.ReaperOSC ~/Library/Application\ Support/REAPER/Scripts/../OSC/Agent.ReaperOSC`
   (i.e. into `~/Library/Application Support/REAPER/OSC/`).
2. REAPER → Preferences → Control/OSC/Web → Add → OSC device:
   UDP, listen on **8000**, send to **127.0.0.1:9000**, pattern config **Agent**.
3. Report back the dialog's exact field labels if they differ — ticket will
   be corrected, and the `reaper.ini` keys recorded for a future doctor check.

## Acceptance (live)

1. `osc-send /play` starts the reference loop; `telemetry --secs 3 --filter
   /time/str` shows advancing timecode; `/track/1/vu` events move while audio
   plays (VU proves the feedback path, not just sends).
2. `osc-send /track/1/volume 0.2` → audible drop + `s`-echo/`n`-feedback
   confirms; `read`-side state consistent on re-render (mix change is real).
3. Tempo: `osc-send /tempo <n>` → read `s/tempo/str` echo; record the
   normalized mapping (or non-mapping) in pitfalls — tempo-set may stay a
   bridge/RPP job if the mapping is hostile.
4. `osc-send /stop` leaves transport stopped; `pytest` green (25 tests).

## Doctor hook (recorded for t4)

Device persists in `reaper.ini` as:
`csurf_0=OSC "Agent" 3 8000 "127.0.0.1" 9000 1024 10 "Agent"`
(`csurf_cnt=1`). Future doctor: pass iff a `csurf_N` line names `"Agent"`.

## Notes

- REAPER track numbering is 1-based over OSC; bridge `track` params are
  0-based. `osc-send` takes the OSC (1-based) form verbatim — no translation
  in the client (documented here, not hidden).
- If VU floods, comment out `TRACK_VU`/`MASTER_VU` first (file header).
