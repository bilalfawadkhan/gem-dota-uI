"""The figure-data exporter: its output folder and its shape against the docs site's own data."""

import json
from pathlib import Path

import pytest

from gemstudio import export, paths, worker

REPO = Path(__file__).resolve().parents[2]
REAL_REPLAY = REPO / "9045456575_334166624.dem"
SITE_DATA = REPO / "site" / "src" / "data"


def run_pipeline(dem: Path, cache: Path) -> tuple[Path, dict]:
    """The job's steps in order (the app runs the three passes in parallel)."""
    summary = worker.run_parse(dem, cache, lambda *_: None)
    folder = Path(summary["folder"])
    export.run_states_pass(dem, folder / "states.json")
    export.run_places_pass(dem, folder / "places.json")
    manifest = export.export_figures(folder, icons=export.icons_dir())
    return folder / "figures-data", manifest


def shape(value, depth=0):
    """The key structure of a JSON value: dict keys recursively, one element of a list."""
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in sorted(value.items())} if depth < 4 else "{...}"
    if isinstance(value, list):
        return [shape(value[0], depth + 1)] if value else []
    return (
        "number"
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else type(value).__name__
    )


def differences(expected, actual, path=""):
    """Keys the site's data has and the export lacks (or the reverse), and type changes."""
    found = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in actual:
                found.append(f"{path}/{key}: missing from the export")
            elif key not in expected:
                found.append(f"{path}/{key}: not in the site's data")
            else:
                found += differences(expected[key], actual[key], f"{path}/{key}")
    elif isinstance(expected, list) and isinstance(actual, list):
        if expected and actual:
            found += differences(expected[0], actual[0], path + "[]")
    elif expected != actual:
        found.append(f"{path}: site {expected} vs export {actual}")
    return found


def test_exports_the_figure_folder_for_the_truncated_fixture(fixture_dem, tmp_path):
    figures, manifest = run_pipeline(fixture_dem, tmp_path)

    assert export.export_is_current(figures)
    assert manifest["fights"] == 0 and manifest["playbacks"] == 0  # the fixture ends at tick 2375
    for name in (
        "dashboard.json",
        "home.json",
        "fights/index.json",
        "objectives.json",
        "wards.json",
        "lead.json",
        "lanes.json",
        "runes.json",
        "manifest.json",
        "figures/map.webp",
        "figures/ward_observer.png",
        "figures/ward_sentry.png",
    ):
        assert (figures / name).is_file(), name
    index = json.loads((figures / "fights" / "index.json").read_text())
    assert index["fights"] == []
    assert json.loads((figures / "home.json").read_text())["map"]["half_line"]
    dashboard = json.loads((figures / "dashboard.json").read_text())
    assert set(dashboard) == {"match", "players", "advantage"}
    assert not list(figures.parent.glob("*.building"))


def test_export_is_atomic_and_reusable(fixture_dem, tmp_path):
    figures, _ = run_pipeline(fixture_dem, tmp_path)
    (figures / "manifest.json").unlink()  # an interrupted export has no manifest
    assert not export.export_is_current(figures)
    export.export_figures(figures.parent, icons=export.icons_dir())
    assert export.export_is_current(figures)


def test_export_refuses_to_run_without_its_inputs(tmp_path):
    with pytest.raises(export.ExportError, match="match.json is missing"):
        export.export_figures(tmp_path)


@pytest.mark.slow
@pytest.mark.skipif(not REAL_REPLAY.is_file(), reason="needs the full replay in the repo root")
def test_real_replay_matches_the_shape_of_the_sites_data():
    """Every figure file has the keys and types the site's committed data has.

    Reads the real cache folder (a cold run takes minutes: the parse plus two passes).
    """
    figures, manifest = run_pipeline(REAL_REPLAY, paths.cache_dir())

    assert manifest["fights"] > 20 and manifest["playbacks"] > 0
    dashboard = json.loads((figures / "dashboard.json").read_text(encoding="utf-8"))
    assert len(dashboard["players"]) == 10 and dashboard["match"]["match_id"] == 9045456575
    assert dashboard["match"]["fights"] == manifest["fights"]
    assert len(dashboard["advantage"]["gold"]) > 30
    for name in ("objectives.json", "wards.json", "lead.json", "lanes.json", "runes.json"):
        expected = shape(json.loads((SITE_DATA / name).read_text(encoding="utf-8")))
        actual = shape(json.loads((figures / name).read_text(encoding="utf-8")))
        assert differences(expected, actual) == [], name

    index = json.loads((figures / "fights" / "index.json").read_text())
    site_index = json.loads((SITE_DATA / "fights" / "index.json").read_text(encoding="utf-8"))
    assert differences(shape(site_index["fights"][0]), shape(index["fights"][0])) == []
    played = next(f for f in index["fights"] if f.get("box"))
    assert (figures / "figures" / "fights" / f"{played['n']}.webp").is_file()
    fight = json.loads((figures / "fights" / f"{played['n']}.json").read_text())
    site_played = next(f for f in site_index["fights"] if f.get("box"))
    site_fight = json.loads((SITE_DATA / site_played["file"]).read_text(encoding="utf-8"))
    # The playback has the hero states the map draws; compare the top-level structure.
    assert set(fight) == set(site_fight)
    assert fight["heroes"] and all(h["runs"] for h in fight["heroes"])
