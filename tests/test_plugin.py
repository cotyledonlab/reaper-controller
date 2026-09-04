"""Agent Plugin conformance (agent-plugins.org v1.0.0, from spec text) +
server inventory. No network: schemas are never retrieved at load."""

import asyncio
import json
import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
PLUGIN_FIELDS = {
    "$schema", "name", "version", "description", "author", "homepage",
    "repository", "license", "keywords", "extensions",
}
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,62}[a-z0-9])?$")

EXPECTED_TOOLS = {
    "reaper_doctor", "reaper_status", "reaper_bridge_send", "reaper_templates",
    "reaper_create", "reaper_read", "reaper_render", "reaper_analyze",
    "reaper_osc_send", "reaper_telemetry", "reaper_compose", "reaper_midi_send",
    "reaper_midi_ports", "reaper_midi_serve_status",
}


def test_manifest_conforms():
    m = json.loads((ROOT / "plugin.json").read_text())
    assert m["$schema"] == PLUGIN_SCHEMA
    assert set(m) <= PLUGIN_FIELDS, set(m) - PLUGIN_FIELDS
    assert NAME_RE.match(m["name"]), m["name"]
    assert "--" not in m["name"] and ".." not in m["name"]
    assert m["version"] and m["description"] and m["license"]


def test_skill_layout():
    skill = ROOT / "skills" / "reaper" / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text()
    assert text.startswith("---")
    head, _ = text.split("---", 2)[1], None
    assert "name:" in head and "description:" in head


def test_mcp_config_conforms():
    m = json.loads((ROOT / "mcp.json").read_text())
    assert m["$schema"] == MCP_SCHEMA
    assert set(m) == {"$schema", "mcpServers"}
    assert isinstance(m["mcpServers"], dict) and m["mcpServers"]
    for _name, srv in m["mcpServers"].items():
        assert srv["type"] == "stdio"
        cmd = srv["command"]
        assert cmd == cmd.strip() and ("./" in cmd or "/" not in cmd)
        assert "env" not in srv or isinstance(srv["env"], dict)
        assert not any("sk-" in str(v) or "token" in str(k).lower() for k, v in srv.get("env", {}).items())
    launcher = ROOT / "bin" / "reaper-connector-server"
    assert launcher.is_file()
    assert launcher.stat().st_mode & stat.S_IXUSR, "launcher must be executable"


def test_server_tools_registered():
    pytest.importorskip("mcp.server.fastmcp")
    from reaper_connector import server as S

    import mcp.server.fastmcp as _fm

    seen: set[str] = set()
    real_tool = _fm.FastMCP.tool

    def spy(self, *a, **k):
        def deco(fn):
            seen.add(fn.__name__)
            return real_tool(self, *a, **k)(fn)

        return deco

    _fm.FastMCP.tool = spy
    real_run = _fm.FastMCP.run
    _fm.FastMCP.run = lambda self, *a, **k: None
    try:
        S.main()
    finally:
        _fm.FastMCP.tool = real_tool
        _fm.FastMCP.run = real_run
    assert EXPECTED_TOOLS <= seen, EXPECTED_TOOLS - seen
