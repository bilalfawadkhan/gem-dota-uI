"""Checks on the packaging files, and on a built bundle when one exists."""

import re
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
BUNDLE = APP / "build" / "dist" / "GemStudio"


def test_the_installer_app_id_never_changes():
    """AppId is how Inno Setup finds an installed copy to upgrade; changing it strands users."""
    iss = (APP / "packaging" / "gemstudio.iss").read_text(encoding="utf-8")
    assert "AppId={{6F0C2F6E-9C4B-4F7A-8B61-3B0E5D2A91C7}" in iss


def test_the_installer_is_per_user_and_does_not_hijack_dem_files():
    iss = (APP / "packaging" / "gemstudio.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss  # no administrator rights needed
    assert "OpenWithProgids" in iss  # listed under "Open with"
    # Never claims the .dem default: that key would take the file type from other programs.
    assert not re.search(r'Subkey: "Software\\Classes\\\.dem"; ValueType: string; ValueData', iss)
    assert "LicenseFile=..\\build\\LICENSES.txt" in iss


def test_the_spec_bundles_what_the_frozen_app_looks_for():
    """paths.py and export.py look for these folders inside the bundle."""
    spec = (APP / "packaging" / "gemstudio.spec").read_text(encoding="utf-8")
    for destination in (
        '"web"',
        '"icons/heroes"',
        '"scripts"',
        '"examples/cookbook"',
        '"assets/maps"',
        '"licenses"',
    ):
        assert destination in spec, destination
    assert 'collect_submodules("gem")' in spec and 'collect_data_files("gem")' in spec
    assert "console=False" in spec  # a desktop app, no console window


def test_the_build_script_parses():
    command = (
        "$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{APP / 'scripts' / 'build_app.ps1'}', [ref]$null, [ref]$e); "
        "if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_licence_notice_carries_the_required_attributions():
    from importlib import util

    spec = util.spec_from_file_location(
        "collect_licenses", APP / "packaging" / "collect_licenses.py"
    )
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = module.NOTICES
    assert "LGPL" in text and "Qt" in text  # PySide6 / Qt
    assert "Valve" in text  # the Dota artwork is not covered by the MIT licence
    assert "Chromium" in text
    assert "SIL Open Font License" in text


def test_the_requirements_pin_every_package_the_bundle_needs():
    pins = (APP / "requirements-build.txt").read_text(encoding="utf-8")
    for name in (
        "numpy",
        "pandas",
        "PySide6",
        "pyinstaller",
        "pillow",
        "python-snappy",
        "zstandard",
    ):
        assert re.search(rf"^{re.escape(name)}==", pins, re.M | re.I), name


@pytest.mark.skipif(not BUNDLE.is_dir(), reason="no build yet (run app/scripts/build_app.ps1)")
def test_a_built_bundle_has_everything_the_app_loads_at_run_time():
    internal = BUNDLE / "_internal"
    for needed in (
        "web/fights.html",
        "web/lanes.html",
        "web/wards.html",
        "icons/heroes/axe.png",
        "icons/ward_observer.png",
        "scripts/export_site_home_data.py",
        "examples/cookbook/fights.py",
        "assets/maps/Game_map_7.41.jpg",
        "gem/data/heroes.json",
        "licenses/LICENSES.txt",
    ):
        assert (internal / needed).is_file(), needed
    assert (BUNDLE / "GemStudio.exe").is_file()
    # The big optional package is deliberately left out until Parquet export is in the UI.
    assert not (internal / "pyarrow").exists()
