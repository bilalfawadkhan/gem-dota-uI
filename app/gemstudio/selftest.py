"""``GemStudio.exe --self-test <replay.dem>``: prove an installed build works end to end.

Runs the real app on a real replay and checks what a user relies on: the replay is read by the
worker processes (native modules, spawn, the bundled exporter and its recipes), the figure data
is written, the dashboard fills in, and every figure tab loads in its web view without a
JavaScript error. It writes a JSON report and exits 0 only if every check passed.

Used by the build script on the frozen app, and by hand on a source checkout. It needs a
display (a normal Windows session); it does not need Python or Node on the machine.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gemstudio import __version__, paths

#: (tab index, page name) in tab order; "lead" may legitimately say there is no data.
TABS = [
    (0, "fights"),
    (1, "objectives"),
    (2, "lanes"),
    (3, "runes"),
    (4, "lead"),
    (5, "wards"),
]


class SelfTest:
    """Collects check results and drives the window."""

    def __init__(self, app: Any, window: Any) -> None:
        self.app = app
        self.window = window
        self.checks: list[dict[str, Any]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        """Record one check."""
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
        return bool(ok)

    def wait(self, condition: Callable[[], bool], timeout_s: float) -> bool:
        """Run the Qt event loop until ``condition()`` is true or the time is up."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if condition():
                return True
            self.app.processEvents()
            time.sleep(0.02)
        return condition()

    def js(self, page: Any, script: str, timeout_s: float = 15.0) -> Any:
        """Run JavaScript in a figure page and return its result (JSON text is parsed by callers)."""
        box: list[Any] = []
        page.page.runJavaScript(script, box.append)
        self.wait(lambda: bool(box), timeout_s)
        return box[0] if box else None


def environment() -> dict[str, Any]:
    """Facts about the build under test, for the report."""
    info: dict[str, Any] = {
        "app_version": __version__,
        "frozen": paths.is_frozen(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "bundle_root": str(paths.bundle_root()),
        "web_dist": str(paths.web_dist()),
    }
    try:
        import PySide6

        info["pyside6"] = PySide6.__version__
    except ImportError:  # pragma: no cover
        pass
    return info


def run(replay: Path, report: Path | None, timeout_s: float = 900.0) -> int:
    """Run the self-test.

    Args:
        replay: A replay to read (the truncated test replay is enough for a quick run; a full
            replay also exercises fight playbacks and the map crops).
        report: Where to write the JSON report, or None for none.
        timeout_s: How long to allow the replay to be read.

    Returns:
        0 if every check passed, 1 otherwise.
    """
    from PySide6.QtWidgets import QApplication

    from gemstudio import scheme, theme
    from gemstudio.window import MainWindow

    scheme.register_scheme()
    app = QApplication([sys.argv[0]])
    theme.apply_theme(app)
    window = MainWindow()
    window.interactive = False  # record errors instead of opening dialogs nobody can close
    window.show()
    test = SelfTest(app, window)
    started = time.monotonic()

    test.check("the bundled figures are present", (paths.web_dist() / "fights.html").is_file(),
               str(paths.web_dist()))  # fmt: skip
    outcome: dict[str, Any] = {}
    window.job.finished.connect(lambda summary: outcome.update(done=summary))
    window.job.failed.connect(lambda error: outcome.update(failed=error))
    window.open_replay(replay)
    finished = test.wait(lambda: bool(outcome), timeout_s)
    test.check("the replay was read", finished and "done" in outcome,
               str(outcome.get("failed", "") if finished else f"no result in {timeout_s:.0f} s"))  # fmt: skip

    if "done" in outcome:
        summary = outcome["done"]
        data_dir = Path(summary["data_dir"])
        read_s = time.monotonic() - started
        test.check("the match was parsed", summary["players"] > 0,
                   f"{summary['players']} players, {summary['fights']} fights, {read_s:.0f} s")  # fmt: skip
        for name in ("dashboard.json", "home.json", "fights/index.json", "figures/map.webp"):
            test.check(f"figure data written: {name}", (data_dir / name).is_file())
        test.check(
            "the dashboard shows the replay", window.stack.currentWidget() is window.dashboard
        )
        test.check("the roster is filled", len(window.dashboard.rail._buttons) > 0
                   or summary.get("parse_error") is not None,
                   f"{len(window.dashboard.rail._buttons)} players")  # fmt: skip
        check_tabs(test, window)

    failed = [c for c in test.checks if not c["ok"]]
    result = {
        "ok": not failed,
        "seconds": round(time.monotonic() - started, 1),
        "environment": environment(),
        "checks": test.checks,
    }
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{'ALL PASSED' if not failed else f'{len(failed)} FAILED'} in {result['seconds']} s")
    window.job.cancel()
    window.close()
    return 0 if not failed else 1


def check_tabs(test: SelfTest, window: Any) -> None:
    """Open every figure tab and check it mounted (or said there is no data) with no JS errors."""
    for index, name in TABS:
        window.sections.setCurrentIndex(index)
        page = window.pages[name]
        mounted = (
            f"document.querySelector('[data-recipe-figure=\"{name}\"] [data-controls]')"
            "?.hidden === false"
        )
        empty = "document.body?.textContent?.includes('No minute-by-minute') === true"
        if name == "fights":  # its list is drawn by the figure itself
            mounted = "document.querySelector('.fights-fig-controls, [data-controls]') !== null"

        def loaded(page: Any = page, mounted: str = mounted, empty: str = empty) -> bool:
            return bool(test.js(page, mounted)) or bool(test.js(page, empty))

        ok = test.wait(loaded, 45)
        test.check(f"figure tab loads: {name}", ok and not page.errors,
                   "; ".join(page.errors[:2]))  # fmt: skip
    test.check("the page bridge connected", window.bridge.is_ready)
