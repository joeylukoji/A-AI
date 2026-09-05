from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import worker  # noqa: E402


class _FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return {"id": "artifact-1"}


class _FakeClient:
    """Minimal httpx.Client stand-in that records every POST."""

    def __init__(self, calls: list[tuple[str, Any]], fail_url_fragments: tuple[str, ...] = ()) -> None:
        self._calls = calls
        self._fail_url_fragments = fail_url_fragments

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def post(self, url: str, headers: dict[str, str] | None = None, json: Any = None) -> _FakeResponse:
        self._calls.append((url, json))
        if any(frag in url for frag in self._fail_url_fragments):
            raise httpx.ConnectError("simulated network failure")
        return _FakeResponse()


def _patch_httpx_client(monkeypatch: pytest.MonkeyPatch, calls: list[tuple[str, Any]], fail_url_fragments=()):
    def factory(*args: object, **kwargs: object) -> _FakeClient:
        return _FakeClient(calls, fail_url_fragments)

    monkeypatch.setattr(worker.httpx, "Client", factory)


def _valid_job(job_id: str = "11111111-1111-1111-1111-111111111111", project_id: str = "22222222-2222-2222-2222-222222222222") -> dict[str, Any]:
    return {
        "job_id": job_id,
        "project_id": project_id,
        "input": {
            "plan_document": {
                "floor": {"height_m": 2.7, "bounds": {"width": 4, "depth": 3}},
                "walls": [],
            },
            "revision_id": None,
        },
    }


def test_process_rejects_non_uuid_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Any]] = []
    _patch_httpx_client(monkeypatch, calls)
    job = _valid_job(job_id="../../etc/passwd")
    worker.process(job, "http://api", "tok")
    # Sans job_id fiable, on ne doit jamais tenter d'appeler l'API interne.
    assert calls == []


def test_process_rejects_path_traversal_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Any]] = []
    _patch_httpx_client(monkeypatch, calls)
    build_called = False

    def fake_build(*a: object, **kw: object) -> None:
        nonlocal build_called
        build_called = True

    monkeypatch.setattr(worker, "_build", fake_build)
    job = _valid_job(project_id="../other-project")
    worker.process(job, "http://api", "tok")

    assert build_called is False
    assert len(calls) == 1
    url, payload = calls[0]
    assert url.endswith("/complete")
    assert payload["status"] == "failed"
    assert "project_id" in payload["error"]


def test_process_cleans_temp_dir_on_build_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Any]] = []
    _patch_httpx_client(monkeypatch, calls)
    created: list[Path] = []
    real_mkdtemp = worker.tempfile.mkdtemp

    def tracking_mkdtemp(*a: object, **kw: object) -> str:
        d = real_mkdtemp(*a, **kw)
        created.append(Path(d))
        return d

    monkeypatch.setattr(worker.tempfile, "mkdtemp", tracking_mkdtemp)

    def failing_build(*a: object, **kw: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "_build", failing_build)

    worker.process(_valid_job(), "http://api", "tok")

    assert created, "expected a temp dir to have been created"
    assert not created[0].exists(), "temp dir must be removed even when the build fails"
    fail_calls = [c for c in calls if c[0].endswith("/complete")]
    assert fail_calls and fail_calls[-1][1]["status"] == "failed"
    assert "blender build failed" in fail_calls[-1][1]["error"]


def test_process_marks_job_failed_when_running_notification_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network blip while posting '/running' must not leave the job stuck.

    Before the fix, an exception here (outside the two inner try/except
    blocks) propagated all the way to the worker main loop and the job was
    never marked failed, staying "running" forever on the API side.
    """
    calls: list[tuple[str, Any]] = []

    # First Client() (used for the main flow) fails on /running; the second
    # Client() (used by _fail) must still succeed so the job gets marked failed.
    clients: list[_FakeClient] = []

    def factory(*args: object, **kwargs: object) -> _FakeClient:
        fail = ("/running",) if not clients else ()
        c = _FakeClient(calls, fail)
        clients.append(c)
        return c

    monkeypatch.setattr(worker.httpx, "Client", factory)

    build_called = False

    def fake_build(*a: object, **kw: object) -> None:
        nonlocal build_called
        build_called = True

    monkeypatch.setattr(worker, "_build", fake_build)

    worker.process(_valid_job(), "http://api", "tok")

    assert build_called is False, "build must not run once the running-notification failed"
    complete_calls = [c for c in calls if c[0].endswith("/complete")]
    assert complete_calls, "the job must be reported failed instead of left hanging"
    assert complete_calls[-1][1]["status"] == "failed"


def test_process_success_cleans_temp_dir_and_reports_succeeded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Any]] = []
    _patch_httpx_client(monkeypatch, calls)
    created: list[Path] = []
    real_mkdtemp = worker.tempfile.mkdtemp

    def tracking_mkdtemp(*a: object, **kw: object) -> str:
        d = real_mkdtemp(*a, **kw)
        created.append(Path(d))
        return d

    monkeypatch.setattr(worker.tempfile, "mkdtemp", tracking_mkdtemp)

    def fake_build(plan: dict, plan_path: Path, obj_path: Path, glb_path: Path) -> None:
        obj_path.write_text("o", encoding="utf-8")
        glb_path.write_bytes(b"g")

    def fake_upload_and_register(client, api, headers, project_id, job_id, revision_id, obj_path, glb_path):
        return {"obj": {"id": "o1"}, "glb": {"id": "g1"}}

    monkeypatch.setattr(worker, "_build", fake_build)
    monkeypatch.setattr(worker, "_upload_and_register", fake_upload_and_register)

    worker.process(_valid_job(), "http://api", "tok")

    assert created and not created[0].exists(), "temp dir must be removed after a successful run too"
    complete_calls = [c for c in calls if c[0].endswith("/complete")]
    assert complete_calls and complete_calls[-1][1]["status"] == "succeeded"


def test_build_raises_on_nonzero_blender_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_STUB", "0")
    monkeypatch.setattr(worker, "which", lambda _bin: "/usr/bin/blender")

    class FakeCompleted:
        returncode = 1
        stdout = b"blender: error: something exploded"

    def fake_run(*a: object, **kw: object) -> FakeCompleted:
        return FakeCompleted()

    monkeypatch.setattr(worker.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="blender exited with 1"):
        worker._build({}, tmp_path / "plan.json", tmp_path / "m.obj", tmp_path / "m.glb")


def test_build_raises_clean_error_on_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_STUB", "0")
    monkeypatch.setattr(worker, "which", lambda _bin: "/usr/bin/blender")

    def fake_run(*a: object, **kw: object):
        raise worker.subprocess.TimeoutExpired(cmd="blender", timeout=1, output=b"stuck")

    monkeypatch.setattr(worker.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="timed out"):
        worker._build({}, tmp_path / "plan.json", tmp_path / "m.obj", tmp_path / "m.glb")


def test_fail_never_raises_when_notification_itself_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def factory(*a: object, **kw: object) -> _FakeClient:
        return _FakeClient([], fail_url_fragments=("/complete",))

    monkeypatch.setattr(worker.httpx, "Client", factory)
    # Must not raise even though the notification itself fails.
    worker._fail("http://api", {}, "job-1", "boom")
