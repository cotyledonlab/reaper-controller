# reaper-controller pitfalls (empirically verified)

Every entry was learned against real REAPER 7.79. Agents: read this before improvising.

## 1. RENDER_FILE paths must be absolute

Relative `RENDER_FILE` resolves against **the RPP's own directory**, not the
caller's CWD — a `scratch/t2-gen.wav` render file in `scratch/song.RPP`
silently lands at `scratch/scratch/t2-gen.wav` with exit 0 and no warning.
`create`/`patch_render_file` therefore resolve to absolute paths; keep render
targets space-free too (RPP render lines are unquoted).

## 2. Never probe with `REAPER --help`

It opens the GUI and hangs the caller. Version comes from `Info.plist`,
CLI flags from a `strings`-style byte scan of the binary.

## 3. ReaScript Lua has no sockets

No `socket`, no HTTP from inside the daemon — hence file-drop JSON-RPC, not
TCP. splitting lanes: files for semantics, OSC for high-rate, Web for gaps.

## 4. OSC tempo is normalized 40+256v, echo is change-only

`n/tempo` 0..1 maps to **40..296 BPM** (`0.5`→168, `0.3125`→120 — verified
live both directions). `/tempo/str` echoes the true BPM, but **only when the
value changes** — a no-op resend gets silence, which looks like a dropped
message. Always trust the echo, not the send; capture *during* the send
(echoes are immediate) or you will miss them.

## 5. No echo for track volume; VU delta is the proof

`/track/N/volume` sets are **not echoed back** (no `/track/N/volume` nor
`/volume/str` feedback, even though the pattern file lists both directions).
Verify mix moves with `/track/N/vu` deltas or re-renders instead. Transport
state *is* announced (`/play` on start, `/stop` on stop).

## 6. OSC tracks are 1-based, bridge tracks are 0-based

`osc-send` takes OSC numbering verbatim (`/track/1/` = first track);
`bridge-send player.*`/`engineer.*` take 0-based indices. The client does
no translation on purpose — the ticket, not hidden logic, says which.

## 7. Device IP must be 127.0.0.1, not 0.0.0.0

In the OSC device dialog, Device IP `0.0.0.0` sends feedback nowhere —
sends still work, so it fails *silent one-way*. The `reaper.ini` line reads
`csurf_0=OSC "Agent" 3 8000 "127.0.0.1" 9000 1024 10 "Agent"`.

## 8. Bridge volume is gain, OSC volume is fader taper

`engineer.set_volume` speaks **D_VOL gain units** (1.0 = unity, exact,
read back observed). OSC `n/track/N/volume` 0..1 is the **fader taper up
to +12 dB** — sending `1.0` parks the track at +12 dB (D_VOL 3.98),
which clips the next render. Never use OSC for exact unity; use the
bridge, and distrust any mix level you set before this pitfall was found.

## 9. TrackFX_GetParamNormalized returns ONE value

Unlike most ReaScript getters (`retval, val`), this one returns just the
normalized double. Destructuring `local _, val = …` silently yields nil
— which then encodes as an empty reply. When a getter returns nil,
suspect the unpacking before the API.

## 10. GetSet_LoopTimeRange2 is void — two returns, no retval

Same trap class as #9: the getter returns `(start, end)`, not
`(retval, start, end)`. Three-variable unpacking silently nils the end
and the crash lands in the *reply builder*, after the setter already
worked — so the symptom (fixed by retry) masks the bug. When a crash
sits in string concatenation, count the returns.

## 11. Loop points don't truncate renders

`project.set_loop 0–4` + render → full 8.0 s. Render bounds follow
`RENDER_RANGE` (entire project), never the loop. Loop is a playback
construct; length control lives in items + `create length_sec` (4 s
song → 4.0 s exact). Don't promise loop-length bounces.

## 12. Sends live on the destination as AUXRECV; folders in ISBUS

A send 0→1 appears only on track 1 as
`AUXRECV <srcidx> ? <vol> …` (src index + volume parsed, rest raw).
`read` derives the send view by inversion. Folder depth rides in
`ISBUS <flag> <depth>` (1 opens, -1 closes). And `LOOP 1` on an *item*
is item-loop, unrelated to project loop points in `SELECTION`.

## 13. Selected take plays — the reader must know lanes

An item with takes `[original, empty-SEL]` plays SILENCE while holding
12 good notes. The first reader kept only the last SOURCE and reported
0 notes, hiding a successful take behind a failed one. `read` now
returns `takes[]` (selected/name/notes) with `notes` = the selected
lane. Verify capture from the file, never from drum-tight assumptions.

## 14. Virtual MIDI ports have identity, not just names

Killing the process that holds a virtual port destroys the endpoint;
a same-named replacement is a STRANGER (new UID). Mappings, enable
states, and device lists all go stale. Rule: one permanent `midi-serve`
owns the port forever; never send through transient ports; re-reset MIDI
devices + re-map + re-enable after any endpoint churn.

## 15. Never punch on beat 0

Immediate phrases occasionally capture nothing (one flake in four
passes); takes with a 1–2 beat count-in land 100%. Transport roll-up
vs first-note race — operational rule until disproven otherwise.

## 16. Same-process MIDI loopback proves nothing

Reading your own virtual out from the same client receives NOTHING
even when cross-process delivery is perfect. Always verify emission
with a second process (or REAPER itself).

## 17. Filenames with spaces break messages

Same lesson as Pd: keep scratch/RPP/WAV paths space-free.
