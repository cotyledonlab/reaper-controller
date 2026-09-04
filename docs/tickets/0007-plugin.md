# 0007 — Agent Plugin package (agent-plugins.org v1.0.0)

Status: Complete (2026-09-04).

Evidence: 47 pytest green (conformance + inventory incl.). Live MCP
handshake through `./bin/reaper-connector-server`: 14 tools listed,
`reaper_status` answered (7.79, daemon alive, OSC configured) — after
fixing the missing `__main__` guard the first probe caught (server exited
instantly). Skill matches pi's loader rules (dir + frontmatter, per its
skills doc). No namespaces guessed, no secrets, no absolute paths.
Depends on: 0001–0006. Supersedes the old t7 plan (bespoke MCP+skill+pi-tools).

## Why a plugin, and what pi gets

agent-plugins.org v1.0.0 standardizes ONE portable package: `plugin.json`
+ `skills/<name>/SKILL.md` (Agent Skills format) + `mcp.json` (portable
server config). Conformant clients load all three with zero per-harness
wiring. Verified against pi's docs: pi loads Agent-Skills skill dirs and
MCP natively, but does NOT implement the plugin.json client (no discovery
in its docs) — so the package is universal going forward, and pi adopts it
via its existing skill-dir + MCP registration paths (documented below, no
guessing at reverse-domain namespaces: v1 defines only skills + MCP
servers, and pi's TS extensions are outside it).

## Scope

1. `plugin.json` (closed schema, exact `$schema`, valid `reaper-controller`
   name), `mcp.json` (`reaper` stdio server via `./bin/` launcher,
   `${PLUGIN_ROOT}` cwd, no secrets), `skills/reaper/SKILL.md` (engineer +
   player recipes, safety path, lane guide, pitfalls index).
2. `src/reaper_connector/server.py`: FastMCP (`mcp>=1.0,<2`, same as
   pd-connector) — 14 tools mirroring the CLI core. `[project.scripts]`
   entry `reaper-connector-server`.
3. `bin/reaper-connector-server`: POSIX launcher (plugin-relative per spec:
   prefers `$PLUGIN_ROOT/.venv`, else system python3 + `src` on path, clear
   error when `mcp` is missing).
4. `tests/test_plugin.py`: manifest/mcp conformance rules from spec text
   (closed fields, name regex, stdio shape, launcher executable), skill
   frontmatter, server tool inventory.
5. README adoption section: plugin clients (drop-in), pi (skill path +
   MCP registration), shell (CLI).

## Acceptance

1. `pytest` green including conformance + server inventory tests.
2. `./bin/reaper-connector-server` boots against the checkout venv
   (MCP handshake smoke via a real client probe, not just import).
3. `skills/reaper/SKILL.md` loads under pi's skill rules (dir + frontmatter).
4. No client-namespace guessing, no secrets in `mcp.json`, no absolute
   paths in plugin files.
