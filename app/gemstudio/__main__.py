"""``python -m gemstudio [replay.dem]`` (or ``GemStudio.exe``): start the desktop app.

GemStudio.exe                         open the app
GemStudio.exe match.dem               open the app on a replay (as when a .dem is double-clicked)
GemStudio.exe --self-test match.dem   check this build end to end, write a report, exit
GemStudio.exe --version
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
import traceback
from pathlib import Path
from types import TracebackType


def _install_crash_log() -> None:
    """Write uncaught errors to the log folder: a windowed build has no console to show them."""
    from gemstudio import paths

    def hook(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> None:
        text = "".join(traceback.format_exception(kind, value, tb))
        try:
            paths.log_dir().mkdir(parents=True, exist_ok=True)
            (paths.log_dir() / "app-crash.log").write_text(text, encoding="utf-8")
        except OSError:
            pass
        sys.__excepthook__(kind, value, tb)

    sys.excepthook = hook


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="GemStudio", add_help=True)
    parser.add_argument("replay", nargs="?", help="a Dota 2 replay (.dem) to open")
    parser.add_argument("--self-test", action="store_true", help="check this build, then exit")
    parser.add_argument("--report", type=Path, help="with --self-test: write a JSON report here")
    parser.add_argument("--timeout", type=float, default=900.0, help="with --self-test: seconds")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    args, _unknown = parser.parse_known_args(argv)  # ignore flags Qt may add
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the app.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        The process exit code.
    """
    args = _parse(sys.argv[1:] if argv is None else argv)
    if args.version:
        from gemstudio import __version__

        print(__version__)
        return 0
    _install_crash_log()
    if args.self_test:
        if not args.replay:
            print(
                "--self-test needs a replay: GemStudio.exe --self-test match.dem", file=sys.stderr
            )
            return 2
        from gemstudio.selftest import run

        return run(Path(args.replay), args.report, args.timeout)

    # Qt must see the scheme before the QApplication exists.
    from PySide6.QtWidgets import QApplication

    from gemstudio import scheme, theme
    from gemstudio.window import MainWindow

    scheme.register_scheme()
    app = QApplication([sys.argv[0]])
    theme.apply_theme(app)
    window = MainWindow()
    window.show()
    if args.replay:
        window.open_replay(args.replay)
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for the parse worker in a frozen Windows build
    sys.exit(main())
