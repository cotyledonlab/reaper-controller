# 0006 — session player: parts, play-in, recorded takes

Status: Complete (2026-09-04, live vs REAPER 7.79/macOS-arm64).

Live evidence: composed vi–IV–I–V → insert → render `ok=true` (after
an engineer assist: fader to 0.5 tamed ReaSynth stacking). Virtual-port
`midi-serve` daemon (enqueue→receipt) replaced per-send transient ports
— endpoint identity is everything. Two silent takes debugged to (a) a
dead-endpoint mapping and (b) my own last-take-wins reader bug, which hid
a GOOD take; takes-aware `read` now reports lanes. Takes with 7 + 4 live
notes captured (`03-PlayerKeys-MIDI`), selected take renders `ok=true`
(peak −2 dB). `get_input` names the listened device (observed). 43 pytest
green. One unreproduced flake: a 4-note immediate phrase captured nothing
(count-in takes land 100% — operational rule: never punch on beat 0).
Depends on: 0001–0005.

## Scope

1. `music.py` (pure, tested): note parse (C4=60), chord spellings + inversions
   (maj/min/dim/aug/maj7/min7/dom7/dim7/sus/add9/6), diatonic progressions
   (major + natural minor, default vi–IV–I–V), strums (down/up, stagger, vel
   slope), basslines (roots-fifths/roots/fifths-up), `compose_part` dispatcher.
2. `midi.py` (needs `midi` extra): virtual-port `PlayerOut`
   (`reaper-connector`, no IAC config) + `phrase` scheduler. Overlapping
   polyphonic lines need a chord-aware scheduler — noted, t7.
3. Bridge `player.rec_arm {track, armed, monitor}` → observed back.
4. CLI: `compose --spec JSON` (notes to stdout, pipe into create/insert),
   `midi-send note|phrase`, `midi-hold --secs` (holds the virtual port open
   while the human maps it), `midi-ports`.
5. Tests: spellings/inversions/progression/strum/bass/dispatcher (no DAW).

## One-time setup (human, ~2 min)

1. Agent runs `midi-hold --secs 60` (virtual `reaper-connector` port appears).
2. Human: AgentSynth track input → MIDI → `reaper-connector` → All channels.
   (Input mapping has no clean ReaScript code — hence manual, like OSC.)
3. Agent owns the rest: `rec_arm`, OSC `/record`, notes, `/stop`.

## Acceptance (live)

1. `compose` vi–IV–I–V → `insert_midi` → render → `analyze ok=true`
   (composed song, not a test riff).
2. Audition: armed + monitored track, `midi-send phrase` (4 notes) → VU
   moves + human hears ReaSynth (no recorded take yet).
3. Take: `rec_arm` + OSC `/record` + phrase + `/stop` → new take exists
   (save + RPP shows second take/item) and renders audible.
4. `pytest` green.
