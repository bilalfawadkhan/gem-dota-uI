"""Where the app finds its files, in a source checkout and in a frozen build.

Frozen (PyInstaller) builds unpack beside the executable (``sys._MEIPASS``); in a
checkout everything is found relative to the repository.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "GemStudio"


def is_frozen() -> bool:
    """Whether the app runs from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Root of the bundled resources (frozen) or of the repository (checkout)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def web_dist() -> Path:
    """The compiled figures (``app/web/dist``), served as ``gem://app/``."""
    if is_frozen():
        return bundle_root() / "web"
    return bundle_root() / "app" / "web" / "dist"


def demo_data_roots() -> list[Path]:
    """Folders holding the docs site's committed demo data, searched in order.

    ``src/data`` has the JSON; ``public`` has ``figures/`` (the map images). Used only
    until a replay has its own exported data folder.
    """
    root = bundle_root()
    if is_frozen():
        return [root / "demo-data"]
    return [root / "site" / "src" / "data", root / "site" / "public"]


def user_data_dir() -> Path:
    """Per-user folder for the cache, logs and settings (never the install folder).

    ``GEMSTUDIO_DATA_DIR`` overrides it (used by the build's smoke test, so a test starts cold
    instead of reusing the developer's cache).
    """
    override = os.environ.get("GEMSTUDIO_DATA_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_NAME


def cache_dir() -> Path:
    """Where parsed replays are cached."""
    return user_data_dir() / "cache"


def log_dir() -> Path:
    """Where error tracebacks from the parse worker are written."""
    return user_data_dir() / "logs"


def hero_icons() -> Path:
    """Folder of hero icons (``<short name>.png``) for the native widgets."""
    if is_frozen():
        return bundle_root() / "icons" / "heroes"
    return bundle_root() / "app" / "web" / "icons" / "heroes"
