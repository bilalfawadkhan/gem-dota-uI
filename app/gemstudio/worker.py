"""The parse job, run in its own process so the UI thread never waits on it.

This module must not import Qt: it is imported by the spawned child. ``run_parse``
does the work and is directly testable; ``worker_main`` is the process entry that
reports to the UI over a queue as ``(kind, payload)`` messages:

- ``("phase", "Parsing replay")``: a progress label (the engine has no finer progress),
- ``("done", summary)``: finished, with a :class:`ParseSummary` dict,
- ``("error", {...})``: failed, with ``kind`` ``"replay"`` (bad or unsupported data) or
  ``"internal"`` (a bug; the traceback is also written to the log folder).
"""

from __future__ import annotations

import hashlib
import json
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gemstudio import __version__


def detach_qt_import_hook() -> None:
    """Restore Python's own import function if Qt has replaced it.

    PyInstaller's PySide6 run-time hook imports Qt in every process of a frozen app, the worker
    processes included. Qt then swaps ``builtins.__import__`` for its ``__feature_import__``, and
    that makes pandas fail to import (``'_SixMetaPathImporter' object has no attribute '_path'``,
    raised while ``dateutil`` loads ``six``). The workers never use Qt, so they put the standard
    function back. Without Qt loaded this does nothing.
    """
    import builtins
    import importlib

    if getattr(builtins.__import__, "__qualname__", "") == "__feature_import__":
        builtins.__import__ = importlib.__import__


# Runs when a worker process imports this module, before it imports pandas or the exporter.
detach_qt_import_hook()

ParseSummary = dict[str, Any]
Report = Callable[[str, Any], None]

CACHE_SCHEMA = 1


def file_digest(path: Path) -> str:
    """SHA-256 of a file's content, read in chunks.

    Args:
        path: The replay file.

    Returns:
        The hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_key(path: Path, engine_version: str) -> str:
    """Cache folder name for a replay: its content and the engine that parsed it."""
    return f"{file_digest(path)[:20]}-{engine_version}-s{CACHE_SCHEMA}"


def run_parse(dem_path: str | Path, cache_root: str | Path, report: Report) -> ParseSummary:
    """Parse a replay (or load it from the cache) and return a summary.

    The parsed match is saved as ``match.json`` in the replay's cache folder, with a
    ``summary.json`` beside it. A replay that ends early is not an error: the engine
    keeps what it read and the summary carries ``parse_error`` and ``truncated_at_tick``.
    A replay that fails before anything is read is an error.

    Args:
        dem_path: The replay file.
        cache_root: The cache folder; a subfolder is made per replay and engine version.
        report: Called with ``(kind, payload)`` progress messages.

    Returns:
        The summary: match id, scores, player count, ``parse_error`` and
        ``truncated_at_tick``, the cache folder, and ``cached`` (true on a cache hit).

    Raises:
        gem.ReplayDataError: If nothing could be read (wrong header, damaged from the start).
    """
    import gem

    path = Path(dem_path)
    report("phase", "Reading replay")
    # The app version is part of the key: a new release may parse differently (the bundled engine
    # reports the same version string for a fork build), so it never reuses older results.
    folder = Path(cache_root) / cache_key(path, f"{gem.__version__}-app{__version__}")
    report("folder", str(folder))  # lets the other passes start while this one parses
    summary_file = folder / "summary.json"
    if summary_file.is_file() and (folder / "match.json").is_file():
        summary: ParseSummary = json.loads(summary_file.read_text(encoding="utf-8"))
        summary["cached"] = True
        return summary

    report("phase", "Parsing replay")
    match = gem.parse(path)
    # gem.parse() does not raise on bad data: it records parse_error and returns a
    # placeholder match. An error with nothing read (tick 0) is a failed replay, not a
    # partial one.
    if match.parse_error and not match.truncated_at_tick:
        raise gem.ReplayDataError(str(match.parse_error))

    report("phase", "Saving results")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "match.json").write_text(gem.to_json(match), encoding="utf-8")
    summary = {
        "replay": str(path),
        "folder": str(folder),
        "match_id": match.match_id,
        "radiant_score": match.radiant_score,
        "dire_score": match.dire_score,
        "radiant_win": match.radiant_win,
        "players": len(match.players),
        "fights": len(match.fights),
        "parse_error": match.parse_error,
        "truncated_at_tick": match.truncated_at_tick,
        "engine_version": gem.__version__,
        "cached": False,
    }
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_task(fn: Callable[[], Any], log_root: str | Path, queue: Any) -> None:
    """Run one job step and put its outcome on ``queue``.

    Puts ``("done", result)`` or ``("error", {...})``: ``kind`` is ``"replay"`` for a
    replay that cannot be read, ``"export"`` for figure data that cannot be written, and
    ``"internal"`` for anything else (the traceback goes to the log folder).

    Args:
        fn: The step to run.
        log_root: Where to write the traceback of an internal failure.
        queue: A ``multiprocessing`` queue the UI reads.
    """
    try:
        result = fn()
    except Exception as exc:
        from gem import ReplayDataError

        from gemstudio.export import ExportError

        if isinstance(exc, ReplayDataError):
            queue.put(("error", {"kind": "replay", "message": str(exc)}))
            return
        if isinstance(exc, ExportError):
            queue.put(("error", {"kind": "export", "message": str(exc)}))
            return
        text = traceback.format_exc()
        log_file = Path(log_root) / "worker-error.log"
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text(text, encoding="utf-8")
        except OSError:
            log_file = Path("")
        queue.put(
            (
                "error",
                {
                    "kind": "internal",
                    "message": f"{type(exc).__name__}: {exc}",
                    "traceback": text,
                    "log": str(log_file),
                },
            )
        )
    else:
        queue.put(("done", result))


def worker_main(dem_path: str, cache_root: str, log_root: str, queue: Any) -> None:
    """Process entry for the main parse: ``run_parse``, reporting to ``queue``."""
    run_task(
        lambda: run_parse(dem_path, cache_root, lambda kind, payload: queue.put((kind, payload))),
        log_root,
        queue,
    )


def states_main(dem_path: str, out_file: str, log_root: str, queue: Any) -> None:
    """Process entry for the hero-states pass."""
    from gemstudio.export import run_states_pass

    queue.put(("phase", "Reading hero movement"))
    run_task(lambda: run_states_pass(dem_path, out_file), log_root, queue)


def places_main(dem_path: str, out_file: str, log_root: str, queue: Any) -> None:
    """Process entry for the building and Roshan positions pass."""
    from gemstudio.export import run_places_pass

    queue.put(("phase", "Locating buildings"))
    run_task(lambda: run_places_pass(dem_path, out_file), log_root, queue)


def export_main(cache_folder: str, log_root: str, queue: Any) -> None:
    """Process entry for writing the figure data."""
    from gemstudio.export import export_figures, export_is_current

    def work() -> dict[str, Any]:
        figures = Path(cache_folder) / "figures-data"
        if export_is_current(figures):
            return {"folder": str(figures), "cached": True}
        queue.put(("phase", "Preparing figures"))
        manifest = export_figures(cache_folder)
        return {"folder": str(figures), "cached": False, **manifest}

    run_task(work, log_root, queue)
