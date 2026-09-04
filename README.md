# reaper-controller

Agent interaction layer for the REAPER DAW — personal **studio engineer** + **session player**, no computer-use.

- **Primary:** Lua bridge daemon inside REAPER (`bridge/agent_bridge.lua`) speaking file-drop JSON-RPC (ReaScript has no sockets).
- **Secondary:** native OSC for high-rate control, stock Web Remote for gaps, `.RPP` files + `-renderproject` for bulk/verify.
- See [`SPEC.md`](SPEC.md) (v0.2, bridge-first) and [`docs/tickets/0001-bridge-doctor.md`](docs/tickets/0001-bridge-doctor.md).

```bash
pip install -e ".[dev]"
reaper-connector doctor --fix   # readiness + create AgentBridge/{in,out,log}
reaper-connector status
# with REAPER running + bridge loaded + OSC device configured:
reaper-connector bridge-send ping | hello | engineer.get_mix | engineer.fx_list ...
reaper-connector create song.RPP --template song --params '{"tempo": 100}'
reaper-connector read song.RPP
reaper-connector render song.RPP [--wav out.wav]   # headless -renderproject
reaper-connector analyze out.wav                   # audible + unclipped?
reaper-connector osc-send /play | /track/1/volume 0.5 | /tempo 0.3125 ...
reaper-connector telemetry --secs 3 [--filter /time/str,/track/1/vu]
reaper-connector compose --spec '{"shape":"progression","key":"C4"}'
reaper-connector midi-serve --detach      # permanent phrase player (once)
reaper-connector midi-send phrase --spec '[...notes...]' --tempo 120
python -m pytest
```

Lane guide: **bridge** = exact verbs with observed-back replies (mix, FX,
MIDI); **OSC** = live console (transport, taper volumes, VU meters);
**files** = songs as text + headless bounces. Gotchas live in
[`docs/pitfalls.md`](docs/pitfalls.md) — read before improvising.

## Adopting the plugin (agent-plugins.org v1.0.0)

This repo **is** the plugin package: `plugin.json` + `skills/reaper/` +
`mcp.json`, with the server behind `./bin/reaper-connector-server`.

- **Plugin clients**: point at this directory — manifest, skill, and server
  are discovered from their fixed locations. No setup beyond the REAPER
  one-timers (bridge daemon, OSC device, MIDI input).
- **pi** (three native paths, pick any): skills via shared dirs (`cp -r
  skills/reaper ~/.pi/agent/skills/` — fully standalone, pitfalls
  bundled under `references/`); MCP via `.mcp.json` → `{ "reaper":
  { "command": "<repo>/bin/reaper-connector-server" } }`; native
  `reaper_*` tools via `pi-extension/reaper-connector.ts` →
  `~/.pi/agent/extensions/` + `/reload` (needs `reaper-connector` on
  PATH or `REAPER_CONNECTOR_BIN`).
  (pi doesn't implement plugin.json discovery; the package stays
  client-agnostic — the extension is plain pi, not spec-governed.)
- **Shell / anything**: `reaper-connector` CLI (above) needs only Python +
  `pip install -e ".[dev]"` (`[midi]`/`[mcp]` extras for play-in/server).
