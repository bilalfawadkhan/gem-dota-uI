"""Runs a replay job in worker processes and reports back through Qt signals.

A full replay is slow to read (a 36-minute match took about three minutes), and the
figures need two more passes over it (hero movement for fight playbacks, building
positions for the objectives). So the job runs three processes at once:

    parse ──┐
    states ─┼─> export ──> finished
    places ─┘

``states`` and ``places`` start as soon as ``parse`` has named the replay's cache folder.
``export`` writes the figure data once all three are done. Each step skips work that is
already cached, so reopening a replay is quick.

The UI thread only polls the queues on a timer, so it never waits on a parse. The engine
reports no finer progress than the steps' phase labels; Cancel terminates every process.
"""

from __future__ import annotations

import multiprocessing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from gemstudio import paths
from gemstudio.worker import export_main, places_main, states_main, worker_main

POLL_MS = 100
PASSES = ("parse", "states", "places")
STEP_NAMES = (*PASSES, "export")


@dataclass
class _Task:
    name: str
    process: Any
    queue: Any
    label: str = ""
    result: Any = None
    done: bool = False


@dataclass
class _Run:
    dem: Path
    tasks: dict[str, _Task] = field(default_factory=dict)
    folder: Path | None = None
    summary: dict[str, Any] | None = None


class ParseJob(QObject):
    """One replay job at a time.

    Signals:
        phase(str): What is running now, e.g. "Parsing replay · Locating buildings".
        steps(dict): Each step's state, ``{"parse": "running", "states": "waiting", ...}``
            (``"waiting"``, ``"running"`` or ``"done"``), whenever one changes.
        finished(dict): The parse summary plus ``data_dir``, the folder of figure data.
        failed(dict): ``{"kind": "replay" | "export" | "internal", "message": ..., ...}``.
        cancelled(): The user cancelled.
    """

    phase = Signal(str)
    steps = Signal(dict)
    finished = Signal(dict)
    failed = Signal(dict)
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None, cache_root: Path | None = None):
        super().__init__(parent)
        self._cache_root = cache_root or paths.cache_dir()
        self._context = multiprocessing.get_context("spawn")
        self._run: _Run | None = None
        self._last_steps: dict[str, str] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    @property
    def running(self) -> bool:
        """Whether a job is in progress."""
        return self._run is not None

    def start(self, dem_path: str | Path) -> None:
        """Start reading ``dem_path`` and preparing its figures.

        Args:
            dem_path: The replay file (already checked by ``precheck``).

        Raises:
            RuntimeError: If a job is already running.
        """
        if self.running:
            raise RuntimeError("A replay is already being read.")
        self._run = _Run(Path(dem_path))
        self._last_steps = {}
        log = str(paths.log_dir())
        self._spawn("parse", worker_main, (str(dem_path), str(self._cache_root), log))
        self._timer.start()

    def cancel(self) -> None:
        """Stop the running job, if any."""
        if not self.running:
            return
        self._stop()
        self.cancelled.emit()

    # -- internals ----------------------------------------------------------------------

    def _spawn(self, name: str, target: Any, args: tuple[Any, ...]) -> None:
        assert self._run is not None
        queue = self._context.Queue()
        process = self._context.Process(target=target, args=(*args, queue), daemon=True)
        process.start()
        self._run.tasks[name] = _Task(name, process, queue)

    def _stop(self) -> None:
        self._timer.stop()
        run, self._run = self._run, None
        if run is None:
            return
        for task in run.tasks.values():
            if task.process.is_alive():
                task.process.terminate()
        for task in run.tasks.values():
            task.process.join(2)

    def _fail(self, error: dict[str, Any]) -> None:
        self._stop()
        self.failed.emit(error)

    def _poll(self) -> None:
        run = self._run
        if run is None:
            return
        for task in list(run.tasks.values()):
            error = self._drain(run, task)
            if error is not None:
                self._fail(error)
                return
        self._emit_steps(run)  # before advancing, so the last step shows done before finished
        self._advance(run)
        if self._run is not None:
            self._emit_steps(run)
            labels = [t.label for t in run.tasks.values() if t.label and not t.done]
            if labels:
                self.phase.emit(" · ".join(labels))

    def _emit_steps(self, run: _Run) -> None:
        states = {
            name: (
                "waiting"
                if name not in run.tasks
                else "done"
                if run.tasks[name].done
                else "running"
            )
            for name in STEP_NAMES
        }
        if states != self._last_steps:
            self._last_steps = states
            self.steps.emit(states)

    def _drain(self, run: _Run, task: _Task) -> dict[str, Any] | None:
        """Read a task's messages; return an error to fail the job, or None."""
        while True:
            try:
                kind, payload = task.queue.get_nowait()
            except Exception:  # queue.Empty
                break
            if kind == "phase":
                task.label = str(payload)
            elif kind == "folder":
                self._start_passes(run, Path(payload))
            elif kind == "done":
                task.done, task.result = True, payload
                task.label = ""
            elif kind == "error":
                return dict(payload)
        if not task.done and not task.process.is_alive() and task.queue.empty():
            return {
                "kind": "internal",
                "message": f"The {task.name} step stopped unexpectedly "
                f"(exit code {task.process.exitcode}).",
            }
        return None

    def _start_passes(self, run: _Run, folder: Path) -> None:
        if run.folder is not None:
            return
        run.folder = folder
        log = str(paths.log_dir())
        self._spawn("states", states_main, (str(run.dem), str(folder / "states.json"), log))
        self._spawn("places", places_main, (str(run.dem), str(folder / "places.json"), log))

    def _advance(self, run: _Run) -> None:
        tasks = run.tasks
        if "export" not in tasks:
            if all(n in tasks and tasks[n].done for n in PASSES):
                run.summary = tasks["parse"].result
                self._spawn("export", export_main, (str(run.folder), str(paths.log_dir())))
            return
        if tasks["export"].done:
            summary = dict(run.summary or {})
            summary["data_dir"] = tasks["export"].result["folder"]
            self._stop()
            self.finished.emit(summary)
