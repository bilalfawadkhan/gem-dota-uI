"""Writes a replay's figure data: the same files the docs site keeps in ``site/src/data``.

The docs site builds its figures from JSON written by ``scripts/export_site_home_data.py``.
This module reuses that script's functions (loaded by path, never copied) but writes into
a per-replay folder the web view reads through ``gem://app/_data/``:

    dashboard.json  home.json  fights/index.json  fights/<n>.json  objectives.json  wards.json
    lead.json  lanes.json  runes.json  figures/map.webp  figures/fights/<n>.webp
    figures/ward_observer.png  figures/ward_sentry.png  manifest.json

The script's own ``main()`` is not used: it re-parses the replay and writes into ``site/``.
Two of its steps read the replay again (hero positions for fight playbacks, building
positions for the objectives figure). Those run as their own passes, in parallel with
the main parse, and their results are cached beside the parsed match.

This module must not import Qt (it runs in worker processes).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from gemstudio import paths
from gemstudio.dashboard_data import build_dashboard

#: Bumped when the layout or content of the exported folder changes, to refresh caches.
EXPORT_VERSION = 2
#: A tick beyond any replay: the passes record the whole game, and windows are cut after.
END_OF_REPLAY = 10**9

_site_export: ModuleType | None = None


class ExportError(RuntimeError):
    """The figure data could not be written; the message is fit to show the user."""


def site_export_script() -> Path:
    """The docs site's exporter script (``scripts/export_site_home_data.py``)."""
    return paths.bundle_root() / "scripts" / "export_site_home_data.py"


def load_site_export() -> ModuleType:
    """Import the site's exporter script by path (it is not part of the ``gem-dota`` package).

    Returns:
        The loaded module, cached for later calls.

    Raises:
        ExportError: If the script is missing.
    """
    global _site_export
    if _site_export is None:
        script = site_export_script()
        if not script.is_file():
            raise ExportError(f"The figure exporter is missing: {script}")
        spec = importlib.util.spec_from_file_location("gem_site_export", script)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["gem_site_export"] = module
        spec.loader.exec_module(module)
        _site_export = module
    return _site_export


def icons_dir() -> Path:
    """Folder holding the ward icons the figures draw (``ward_observer.png``, ``ward_sentry.png``)."""
    if paths.is_frozen():
        return paths.bundle_root() / "icons"
    return paths.bundle_root() / "site" / "src" / "assets" / "icons"


# -- the two extra passes over the replay -------------------------------------------------


def run_states_pass(dem_path: str | Path, out_file: str | Path) -> dict[str, Any]:
    """Record every hero's position, HP and mana on every replay packet, for the whole game.

    Fight playbacks need these, and which fights get one is only known after the main
    parse, so the pass records everything and the export cuts the windows afterwards.

    Args:
        dem_path: The replay file.
        out_file: Where to write the states as JSON (``{player_id: [[tick, x, y, ...], ...]}``).

    Returns:
        ``{"file": ..., "cached": bool, "heroes": int}``.
    """
    out = Path(out_file)
    if out.is_file():
        return {"file": str(out), "cached": True}
    ex = load_site_export()
    states = ex.load_hero_states(Path(dem_path), [(0, END_OF_REPLAY)])
    _write_atomic(out, json.dumps({str(k): v for k, v in states.items()}, separators=(",", ":")))
    return {"file": str(out), "cached": False, "heroes": len(states)}


def run_places_pass(dem_path: str | Path, out_file: str | Path) -> dict[str, Any]:
    """Record where buildings stand and where Roshan and the Tormentors were, for the whole game.

    Args:
        dem_path: The replay file.
        out_file: Where to write the places as JSON.

    Returns:
        ``{"file": ..., "cached": bool}``.
    """
    out = Path(out_file)
    if out.is_file():
        return {"file": str(out), "cached": True}
    ex = load_site_export()
    places = ex.load_map_places(Path(dem_path), END_OF_REPLAY)
    _write_atomic(out, json.dumps(places, separators=(",", ":")))
    return {"file": str(out), "cached": False}


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


# -- the export ---------------------------------------------------------------------------


def _within(states: dict[int, list], windows: list[tuple[int, int]]) -> dict[int, list]:
    """Keep only the readings inside the playback windows, as the site's own pass does."""
    return {
        player_id: [
            tuple(reading)
            for reading in readings
            if any(start <= reading[0] <= end for start, end in windows)
        ]
        for player_id, readings in states.items()
    }


def _load_places(file: Path, match: Any) -> dict[str, Any]:
    """Read the places pass, limited as the site's script limits it.

    The site reads the entities only up to 30 ticks after the last objective, so Roshan
    and Tormentor positions after that are left out, and a match with no objective has
    no places at all.
    """
    last = max(
        [t.tick for t in match.towers]
        + [b.tick for b in match.barracks]
        + [r.tick for r in match.roshans]
        + [t.tick for t in match.tormentors],
        default=None,
    )
    if last is None:
        return {}
    raw = json.loads(file.read_text(encoding="utf-8"))
    places: dict[str, Any] = {
        "buildings": {k: tuple(v) for k, v in raw.get("buildings", {}).items()},
        "wisdom": [tuple(p) for p in raw.get("wisdom", [])],
    }
    for kind in ("roshan", "tormentor"):
        places[kind] = [tuple(p) for p in raw.get(kind, []) if p[0] <= last + 30]
    return places


def export_is_current(folder: str | Path) -> bool:
    """Whether a replay's figure data folder is complete and made by this exporter version."""
    manifest = Path(folder) / "manifest.json"
    if not manifest.is_file():
        return False
    try:
        return (
            json.loads(manifest.read_text(encoding="utf-8")).get("export_version") == EXPORT_VERSION
        )
    except (OSError, ValueError):
        return False


def export_figures(
    cache_folder: str | Path, out_folder: str | Path | None = None, *, icons: Path | None = None
) -> dict[str, Any]:
    """Write the figure data for a parsed replay.

    Reads ``match.json``, ``states.json`` and ``places.json`` from the replay's cache
    folder and writes the figure data folder (default ``<cache folder>/figures-data``).
    The folder is built beside its final place and renamed when complete, so a cancelled
    export never leaves a half-written folder that looks finished.

    Args:
        cache_folder: The replay's cache folder (see ``worker.run_parse``).
        out_folder: Where to write; defaults to ``figures-data`` inside ``cache_folder``.
        icons: Folder with the ward icons; defaults to the bundled ones.

    Returns:
        The manifest: export version, match id, the fights written (``fights``, and how
        many have a playback), and any ``warnings``.

    Raises:
        ExportError: If an input is missing or a figure cannot be built.
    """
    import gem

    source = Path(cache_folder)
    final = Path(out_folder) if out_folder else source / "figures-data"
    work = final.with_name(final.name + ".building")
    for needed in ("match.json", "states.json", "places.json"):
        if not (source / needed).is_file():
            raise ExportError(f"Cannot write figures: {needed} is missing from {source}.")

    ex = load_site_export()
    match = gem.load_json(source / "match.json")
    states_all = {
        int(k): [tuple(r) for r in v]
        for k, v in json.loads((source / "states.json").read_text(encoding="utf-8")).items()
    }
    places = _load_places(source / "places.json", match)

    shutil.rmtree(work, ignore_errors=True)
    (work / "fights").mkdir(parents=True)
    warnings: list[str] = []

    def write(name: str, data: Any, *, indent: int | None = None) -> None:
        text = json.dumps(data, indent=indent, separators=None if indent else (",", ":"))
        (work / name).write_text(text + "\n", encoding="utf-8")

    try:
        write("home.json", {"match": ex.match_snapshot(match), "map": ex.map_overlay()}, indent=1)

        # Fights: every fight gets a breakdown; the bigger ones also a map playback.
        in_order = sorted(match.fights, key=lambda f: f.start_tick)
        played = [f for f in in_order if f.deaths >= ex.PLAYBACK_MIN_DEATHS]
        smokes = gem.build_smoke_analysis(match) if played else []
        windows = [ex.playback_window(match, f, smokes) for f in played]
        states = _within(states_all, windows)
        files: dict[int, str] = {}
        boxes: dict[int, list[float]] = {}
        crops = work / "figures" / "fights"
        for number, each in enumerate(in_order, start=1):
            has_playback = any(each is f for f in played)
            if has_playback:
                boxes[number] = ex.fight_box(match, each, states)
                ex.write_map_image(crops / f"{number}.webp", boxes[number], px=800, webp=True)
            data_file = ex.fight_playback(match, states if has_playback else {}, each)
            files[number] = f"fights/{number}.json"
            (work / "fights" / f"{number}.json").write_text(
                json.dumps(data_file, separators=(",", ":")) + "\n", encoding="utf-8"
            )
        end_tick = match.post_game_tick or match.game_end_tick or 0
        write(
            "fights/index.json",
            {
                "start_s": -90.0,
                "end_s": round(ex._game_seconds(match, end_tick), 1),
                "fights": ex.fights_recipe(match, files, boxes),
            },
        )

        write("dashboard.json", build_dashboard(match))
        write("objectives.json", ex.objectives_recipe(match, places))
        write("wards.json", ex.wards_recipe(match))
        write("lead.json", ex.lead_recipe(match))
        write("lanes.json", ex.lanes_recipe(match))
        write("runes.json", ex.runes_recipe(match))
        (work / "figures").mkdir(exist_ok=True)
        ex.write_public_figures(work / "figures", icons or icons_dir())
    except ExportError:
        raise
    except Exception as exc:
        shutil.rmtree(work, ignore_errors=True)
        raise ExportError(f"Could not write the figure data: {type(exc).__name__}: {exc}") from exc

    manifest = {
        "export_version": EXPORT_VERSION,
        "match_id": match.match_id,
        "engine_version": gem.__version__,
        "fights": len(in_order),
        "playbacks": len(played),
        "warnings": warnings,
    }
    write("manifest.json", manifest, indent=1)  # last: its presence means the folder is complete
    shutil.rmtree(final, ignore_errors=True)
    work.replace(final)
    return manifest
