from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import homekit_build  # noqa: E402
import worker  # noqa: E402

PLAN = {"floor": {"bounds": {"width": 6, "depth": 5}}, "walls": [], "rooms": [], "openings": []}


@pytest.fixture
def fake_lib(tmp_path, monkeypatch):
    (tmp_path / "homekit3d").mkdir()
    (tmp_path / "homekit3d" / "cli.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("HOMEKIT_DIR", str(tmp_path))
    return tmp_path


def test_the_library_is_found_in_the_repo_by_default(monkeypatch):
    monkeypatch.delenv("HOMEKIT_DIR", raising=False)
    assert (homekit_build.library_dir() / "homekit3d" / "cli.py").exists()


def test_a_missing_library_disables_the_builder(monkeypatch, tmp_path):
    monkeypatch.setenv("HOMEKIT_DIR", str(tmp_path))
    monkeypatch.setattr(homekit_build, "_DEV_DIR", tmp_path / "nope")
    monkeypatch.setattr(homekit_build.Path, "exists", lambda self: False)
    assert homekit_build.library_dir() is None and homekit_build.enabled() is False


@pytest.mark.parametrize("value,expected", [("0", False), ("off", False), ("FALSE", False), ("no", False), ("1", True), ("", True)])
def test_the_flag_switches_the_builder_off(fake_lib, monkeypatch, value, expected):
    monkeypatch.setenv("HOMEKIT3D", value)
    assert homekit_build.enabled() is expected


def test_build_runs_blender_with_a_clean_startup_and_an_empty_stdin(fake_lib, monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        (tmp_path / "m.obj").write_text("o", encoding="utf-8")
        (tmp_path / "m.glb").write_bytes(b"glTF")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"noise\nHOMEKIT_STATS {\"a\": 1}\n")

    monkeypatch.setattr(homekit_build.subprocess, "run", fake_run)
    monkeypatch.setattr(homekit_build, "which", lambda _: "/usr/bin/blender")
    stats = homekit_build.build(tmp_path / "p.json", tmp_path / "m.obj", tmp_path / "m.glb", blender_bin="blender", timeout=99)
    assert stats == 'HOMEKIT_STATS {"a": 1}'
    cmd = seen["cmd"]
    assert "--factory-startup" in cmd and "--in-blender" in cmd and cmd[cmd.index("--obj") + 1].endswith("m.obj")
    assert seen["kw"]["stdin"] == subprocess.DEVNULL and seen["kw"]["timeout"] == 99
    assert str(fake_lib) in seen["kw"]["env"]["PYTHONPATH"]


def test_the_llm_can_be_switched_off_for_the_build(fake_lib, monkeypatch, tmp_path):
    monkeypatch.setenv("HOMEKIT_LLM", "0")
    seen = {}
    monkeypatch.setattr(homekit_build.subprocess, "run", lambda cmd, **kw: seen.setdefault("cmd", cmd) and subprocess.CompletedProcess(cmd, 1, stdout=b""))
    monkeypatch.setattr(homekit_build, "which", lambda _: "/x")
    with pytest.raises(RuntimeError):
        homekit_build.build(tmp_path / "p", tmp_path / "o", tmp_path / "g", blender_bin="blender", timeout=1)
    assert "--no-ai" in seen["cmd"]


@pytest.mark.parametrize("returncode,stdout", [(1, b"boom"), (11, b"crash")])
def test_a_failing_build_raises_with_the_end_of_the_output(fake_lib, monkeypatch, tmp_path, returncode, stdout):
    monkeypatch.setattr(homekit_build.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, returncode, stdout=stdout))
    monkeypatch.setattr(homekit_build, "which", lambda _: "/x")
    with pytest.raises(RuntimeError, match=str(returncode)):
        homekit_build.build(tmp_path / "p", tmp_path / "o", tmp_path / "g", blender_bin="blender", timeout=1)


def test_a_build_that_writes_nothing_is_an_error(fake_lib, monkeypatch, tmp_path):
    monkeypatch.setattr(homekit_build.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=b""))
    monkeypatch.setattr(homekit_build, "which", lambda _: "/x")
    with pytest.raises(RuntimeError, match="did not produce"):
        homekit_build.build(tmp_path / "p", tmp_path / "o", tmp_path / "g", blender_bin="blender", timeout=1)


def test_a_timeout_is_reported(fake_lib, monkeypatch, tmp_path):
    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(homekit_build.subprocess, "run", slow)
    monkeypatch.setattr(homekit_build, "which", lambda _: "/x")
    with pytest.raises(RuntimeError, match="timed out"):
        homekit_build.build(tmp_path / "p", tmp_path / "o", tmp_path / "g", blender_bin="blender", timeout=1)


# --- le worker --------------------------------------------------------------------------------------
def _worker_env(monkeypatch):
    monkeypatch.setenv("AI_STUB", "0")
    monkeypatch.setattr(worker, "which", lambda _: "/usr/bin/blender")


def test_the_worker_uses_the_library_first(monkeypatch, tmp_path):
    _worker_env(monkeypatch)
    calls = []
    monkeypatch.setattr(worker.homekit_build, "enabled", lambda: True)
    monkeypatch.setattr(worker.homekit_build, "build", lambda *a, **k: calls.append("homekit") or "HOMEKIT_STATS {}")
    monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: calls.append("legacy"))
    worker._build(PLAN, tmp_path / "p.json", tmp_path / "m.obj", tmp_path / "m.glb")
    assert calls == ["homekit"]


def test_the_worker_falls_back_to_the_legacy_builder_when_the_library_fails(monkeypatch, tmp_path):
    _worker_env(monkeypatch)
    calls = []

    def boom(*a, **k):
        (tmp_path / "m.glb").write_bytes(b"partial")
        raise RuntimeError("crash")

    def legacy(cmd, **kw):
        calls.append("legacy")
        (tmp_path / "m.obj").write_text("o", encoding="utf-8")
        (tmp_path / "m.glb").write_bytes(b"glTF")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"")

    monkeypatch.setattr(worker.homekit_build, "enabled", lambda: True)
    monkeypatch.setattr(worker.homekit_build, "build", boom)
    monkeypatch.setattr(worker.subprocess, "run", legacy)
    worker._build(PLAN, tmp_path / "p.json", tmp_path / "m.obj", tmp_path / "m.glb")
    assert calls == ["legacy"] and (tmp_path / "m.glb").read_bytes() == b"glTF"      # le fichier partiel n'a pas survécu


def test_the_worker_skips_the_library_when_it_is_disabled(monkeypatch, tmp_path):
    _worker_env(monkeypatch)
    calls = []
    monkeypatch.setattr(worker.homekit_build, "enabled", lambda: False)
    monkeypatch.setattr(worker.homekit_build, "build", lambda *a, **k: calls.append("homekit"))

    def legacy(cmd, **kw):
        calls.append("legacy")
        (tmp_path / "m.obj").write_text("o", encoding="utf-8")
        (tmp_path / "m.glb").write_bytes(b"glTF")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"")

    monkeypatch.setattr(worker.subprocess, "run", legacy)
    worker._build(PLAN, tmp_path / "p.json", tmp_path / "m.obj", tmp_path / "m.glb")
    assert calls == ["legacy"]


def test_the_stub_mode_never_starts_blender(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_STUB", "1")
    monkeypatch.setattr(worker.homekit_build, "build", lambda *a, **k: pytest.fail("ne doit pas être appelé"))
    worker._build({"floor": {"height_m": 2.7}, "walls": [], "furniture": []}, tmp_path / "p.json", tmp_path / "m.obj", tmp_path / "m.glb")
    assert (tmp_path / "m.obj").exists()
