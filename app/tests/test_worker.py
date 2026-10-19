import queue

import gem
import pytest

from gemstudio import worker


def test_parses_and_summarises_a_truncated_replay(fixture_dem, tmp_path):
    messages = []
    summary = worker.run_parse(
        fixture_dem, tmp_path, lambda kind, payload: kind == "phase" and messages.append(payload)
    )

    assert summary["cached"] is False
    assert summary["players"] == 10
    # A truncated replay is not an error: the engine keeps what it read and says so.
    assert summary["parse_error"]
    assert summary["truncated_at_tick"] == 2375
    assert (tmp_path / summary["folder"].split("\\")[-1] / "match.json").is_file()
    assert messages == ["Reading replay", "Parsing replay", "Saving results"]


def test_saved_match_loads_back(fixture_dem, tmp_path):
    summary = worker.run_parse(fixture_dem, tmp_path, lambda *_: None)
    match = gem.load_json(f"{summary['folder']}/match.json")
    assert len(match.players) == summary["players"]


def test_second_run_uses_the_cache(fixture_dem, tmp_path):
    worker.run_parse(fixture_dem, tmp_path, lambda *_: None)
    messages = []
    summary = worker.run_parse(
        fixture_dem, tmp_path, lambda kind, payload: kind == "phase" and messages.append(payload)
    )
    assert summary["cached"] is True
    assert "Parsing replay" not in messages


def test_cache_is_keyed_by_content_and_engine_version(fixture_dem, tmp_path):
    other = tmp_path / "copy.dem"
    other.write_bytes(fixture_dem.read_bytes())
    assert worker.cache_key(other, "1.0") == worker.cache_key(fixture_dem, "1.0")
    assert worker.cache_key(other, "1.0") != worker.cache_key(other, "2.0")


def test_a_replay_that_fails_before_anything_is_read_is_an_error(tmp_path):
    """gem.parse() itself returns a placeholder match here; the worker must not treat it as success."""
    junk = tmp_path / "junk.dem"
    junk.write_bytes(b"definitely not PBDEMS2")
    with pytest.raises(gem.ReplayDataError):
        worker.run_parse(junk, tmp_path / "cache", lambda *_: None)


def test_worker_main_reports_a_data_error_without_a_traceback(tmp_path):
    junk = tmp_path / "junk.dem"
    junk.write_bytes(b"definitely not PBDEMS2")
    out: queue.Queue = queue.Queue()
    worker.worker_main(str(junk), str(tmp_path / "cache"), str(tmp_path / "logs"), out)
    messages = []
    while not out.empty():
        messages.append(out.get())
    kind, payload = messages[-1]
    assert kind == "error" and payload["kind"] == "replay"
    assert not (tmp_path / "logs").exists()


def test_worker_main_logs_an_internal_failure(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("bug in an extractor")

    monkeypatch.setattr(worker, "run_parse", boom)
    out: queue.Queue = queue.Queue()
    worker.worker_main("x.dem", str(tmp_path / "cache"), str(tmp_path / "logs"), out)
    kind, payload = out.get()
    assert kind == "error" and payload["kind"] == "internal"
    assert "RuntimeError" in payload["message"]
    assert "bug in an extractor" in (tmp_path / "logs" / "worker-error.log").read_text()


def test_the_worker_can_import_pandas_even_when_qt_was_loaded_first():
    """Regression: PyInstaller loads Qt in every process, and Qt's import hook breaks pandas.

    Reproduced from source with a bare ``import PySide6.QtCore``; importing the worker module
    must put Python's import function back so the exporter's ``import pandas`` works.
    """
    import subprocess
    import sys
    from pathlib import Path

    app = Path(__file__).resolve().parents[1]
    code = "import PySide6.QtCore; import gemstudio.worker; import pandas; print('ok')"
    ok = subprocess.run([sys.executable, "-c", code], cwd=app, capture_output=True, text=True)
    assert ok.returncode == 0 and "ok" in ok.stdout, ok.stderr[-400:]
    # The control: without the worker module, the same import fails (this is the bug).
    control = "import PySide6.QtCore; import pandas"
    bad = subprocess.run([sys.executable, "-c", control], cwd=app, capture_output=True, text=True)
    assert bad.returncode != 0 and "_SixMetaPathImporter" in bad.stderr


def test_detaching_the_hook_does_nothing_when_qt_is_not_loaded():
    import builtins

    before = builtins.__import__
    worker.detach_qt_import_hook()
    assert builtins.__import__ is before or builtins.__import__.__qualname__ != "__feature_import__"
