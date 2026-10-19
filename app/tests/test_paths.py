import sys
from pathlib import Path

from gemstudio import paths


def test_source_layout_points_into_the_repository():
    assert paths.is_frozen() is False
    root = paths.bundle_root()
    assert (root / "scripts" / "export_site_home_data.py").is_file()
    assert paths.web_dist() == root / "app" / "web" / "dist"
    assert paths.hero_icons() == root / "app" / "web" / "icons" / "heroes"


def test_a_frozen_build_looks_beside_the_executable(monkeypatch, tmp_path):
    """PyInstaller sets sys.frozen and sys._MEIPASS; everything is then found under that folder."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.is_frozen() is True
    assert paths.bundle_root() == tmp_path
    assert paths.web_dist() == tmp_path / "web"
    assert paths.hero_icons() == tmp_path / "icons" / "heroes"
    assert paths.demo_data_roots() == [tmp_path / "demo-data"]
    from gemstudio.export import icons_dir, site_export_script

    assert icons_dir() == tmp_path / "icons"
    assert site_export_script() == tmp_path / "scripts" / "export_site_home_data.py"


def test_user_data_never_lives_in_the_install_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMSTUDIO_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert paths.user_data_dir() == tmp_path / "GemStudio"
    assert paths.cache_dir() == tmp_path / "GemStudio" / "cache"
    assert paths.log_dir() == tmp_path / "GemStudio" / "logs"


def test_the_data_folder_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMSTUDIO_DATA_DIR", str(tmp_path / "cold"))
    assert paths.cache_dir() == Path(tmp_path / "cold" / "cache")
