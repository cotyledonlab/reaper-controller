"""Doctor readiness tests. Require the eval install on this Mac; skip cleanly elsewhere."""

import pytest

from reaper_connector import doctor

pytestmark = pytest.mark.skipif(
    not doctor.BIN_PATH.is_file(), reason="REAPER not installed"
)


def test_binary_and_version():
    rep = doctor.report()
    assert rep["binary_present"] is True
    assert rep["version"] is not None
    assert rep["version"].startswith("7."), rep["version"]


def test_resource_and_osc_files():
    rep = doctor.report()
    assert rep["resource_present"] is True
    assert all(rep["osc_files"].values()), rep["osc_files"]


def test_render_flags_verified_in_binary():
    rep = doctor.report()
    assert rep["render_flags"]["renderproject"] is True
    assert rep["render_flags"]["batchconvert"] is True


def test_overall_ok():
    assert doctor.report()["ok"] is True


def test_fix_creates_bridge_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("REAPER_RESOURCE_PATH", str(tmp_path))
    result = doctor.fix()
    for name in ("in", "out", "log"):
        assert (tmp_path / "AgentBridge" / name).is_dir()
    assert result["bridge"]["dirs"] == {"in": True, "out": True, "log": True}


def test_osc_device_parse(tmp_path, monkeypatch):
    monkeypatch.setenv("REAPER_RESOURCE_PATH", str(tmp_path))
    ini = tmp_path / "reaper.ini"
    ini.write_text('[reaper]\nfoo=1\n')
    assert doctor.osc_device_configured(tmp_path)["configured"] is False
    ini.write_text('csurf_0=OSC "Agent" 3 8000 "127.0.0.1" 9000 1024 10 "Agent"\ncsurf_cnt=1\n')
    got = doctor.osc_device_configured(tmp_path)
    assert got["configured"] is True
    assert "8000" in got["line"]
