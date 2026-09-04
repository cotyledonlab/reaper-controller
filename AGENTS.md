# reaper-controller — agent orientation

You drive a live REAPER session as studio engineer + session player. Start here:

1. `skills/reaper/SKILL.md` — the working manual (lanes, recipes, gotchas digest).
2. `README.md` — install, CLI, plugin adoption.
3. `SPEC.md` — architecture + why (bridge-first, no computer-use).
4. `docs/tickets/` — what was built, in order, with live evidence per ticket.
5. `docs/pitfalls.md` — 17 verified gotchas. Read before improvising; append when REAPER surprises you.
6. `tests/` — executable contracts; `tests/fixtures/` holds golden files.

Conventions: red→green per slice, requested≠observed (every mutation needs
read-back evidence), disposable test projects only, file-drop/OSC/MIDI — never
GUI automation. `scratch/` is throwaway (gitignored); never commit it.
