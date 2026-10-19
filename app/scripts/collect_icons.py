"""Collect every hero and item icon into ``app/web/icons`` for the figures' build.

The docs site only keeps the icons its demo match uses; the app needs all of them, since any
replay can be opened. The icons are downloaded (not committed) by the repo's own scripts:

    python scripts/fetch_hero_icons.py   # -> src/gem/data/hero_icons/
    python scripts/fetch_item_icons.py   # -> src/gem/data/item_icons/

Run this after them, before ``npm run build`` in ``app/web``::

    python app/scripts/collect_icons.py

Icons belong to Valve; check the terms before redistributing a build that bundles them.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCES = {
    "heroes": REPO / "src" / "gem" / "data" / "hero_icons",
    "items": REPO / "src" / "gem" / "data" / "item_icons",
}
TARGET = REPO / "app" / "web" / "icons"


def main() -> int:
    """Copy the icons; fail with the command to run when a set has not been downloaded."""
    missing = [name for name, folder in SOURCES.items() if not any(folder.glob("*.png"))]
    if missing:
        print(
            f"No {', '.join(missing)} icons found. Run scripts/fetch_hero_icons.py and "
            "scripts/fetch_item_icons.py first.",
            file=sys.stderr,
        )
        return 1
    for kind, folder in SOURCES.items():
        target = TARGET / kind
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        icons = sorted(folder.glob("*.png"))
        for icon in icons:
            shutil.copyfile(icon, target / icon.name)
        print(f"{kind}: {len(icons)} icons -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
