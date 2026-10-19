import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

# pandas must load before Qt WebEngine does: when test_shell.py imports PySide6 at
# collection, a later first import of pandas (by the exporter) fails on Windows with
# "partially initialized module 'pandas'". The app itself is not affected: its UI process
# never imports pandas; the worker processes do, and they never import Qt.
import pandas  # noqa: F401, I001
import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "ti14_finals_g3_xg_vs_falcons_truncated.dem"


@pytest.fixture(scope="session")
def fixture_dem() -> Path:
    """The truncated replay committed with the engine's tests."""
    assert FIXTURE.is_file(), FIXTURE
    return FIXTURE


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the session, with the app's theme (scheme registered at collection)."""
    from PySide6.QtWidgets import QApplication

    from gemstudio import theme

    app = QApplication.instance() or QApplication(["gem-studio-tests"])
    theme.apply_theme(app)
    return app
