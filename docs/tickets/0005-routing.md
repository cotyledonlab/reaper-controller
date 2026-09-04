# 0005 — routing, folders, markers, loop (bridge + read)

Status: Complete (2026-09-04, live vs REAPER 7.79/macOS-arm64).

Live evidence: folder pair (depths 1/-1 observed), send 0→1 @ 0.8
(list_sends + file agree), marker `chorus @8s` listed, loop 0–4 set +
observed (setter survived the reply-crash that exposed the void-return
shape — fixed). Save-diff taught `read`: ISBUS folder encoding,
AUXRECV-on-destination sends, MARKER lines, SELECTION==loop storage.
Renders: loop set → still 8.0 s (loop never truncates render);
constructed 4 s song → 4.0 s exact. 31 pytest green.
Depends on: 0001–0004.

## Scope decision: web deferred with evidence

SPEC imagined a Web Remote HTTP client for gap actions.Live evidence says
`ACTION i/action` over OSC already covers that job (rewind 40042, transport,
metronome-class toggles) with **zero extra setup** — Web Remote would need
another manual enable + token for no new capability. Web stays an option;
t5 spends the slice on routing instead.

## Scope

1. Lua v4 ops:
   - `engineer.set_folder {track, depth}` — 1 = folder start, 0 = normal,
     -1 = last in folder; `{requested, observed}` via `I_FOLDERDEPTH`.
   - `engineer.add_send {from, to, volume?}` — `{send_index,
     observed_volume}` (0-based track indices, bridge convention).
   - `engineer.list_sends {track}` — observed `[{index, dest_track,
     volume, mute}]` via `GetTrackNumSends` + `GetTrackSendInfo_Value`.
   - `project.add_marker {position_sec, name}` / `project.list_markers`.
   - `project.set_loop {start_sec, end_sec}` / `project.get_loop` —
     observed read-back (repeat toggle has no clean API — noted, skipped).
2. Grounding loop (same as t2): apply live → save → **diff the RPP** →
   extend `rpp.read` for whatever REAPER actually wrote (sends/recvs,
   folder depth, markers, loop). Fixtures from the live diff go to
   `tests/fixtures/`.
3. Render check for the loop region via whichever bounds mechanism the
   save-diff reveals (fallback: constructed short song renders exact length).

## Reload (v3 → v4)

`bridge-send bridge.shutdown`, then Actions → run `agent_bridge.lua` again
(deployed to `Scripts/`).

## Acceptance

1. Folder: track 0 depth 1 + new track depth -1 → observed back; `read`
   reports the folder structure.
2. Send: AgentSynth → new bus track, vol observed; `read` shows the send.
3. Marker `@8s "chorus"` listed observed with position + name.
4. Loop 0–4 s set + observed; loop-length render path demonstrated (or
   documented fallback with reason).
5. `pytest` green; pitfalls for every surprise.
