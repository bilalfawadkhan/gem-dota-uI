"""The figure pages: one web view per figure, each in its own tab.

Each page is a compiled figure from ``app/web`` (``gem://app/<name>.html``) reading the open
replay's data from ``gem://app/_data/``. A page owns its web view and its own bridge. Pages
are created the first time their tab is shown and reloaded when a different replay is opened,
so a replay's figures that nobody looks at cost nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from gemstudio import scheme
from gemstudio.bridge import Bridge

DATA_URL = f"gem://{scheme.HOST}/_data"


@dataclass(frozen=True)
class PageSpec:
    """A figure page and its tab.

    Attributes:
        name: The page's name; its file is ``<name>.html`` in the compiled figures.
        title: The tab's label.
    """

    name: str
    title: str


#: The figure tabs, in tab order.
FIGURE_PAGES = (
    PageSpec("fights", "Fight Replay & Dashboard"),
    PageSpec("objectives", "Objectives"),
    PageSpec("lanes", "Lanes"),
    PageSpec("runes", "Runes"),
    PageSpec("lead", "Gold & XP Lead"),
    PageSpec("wards", "Wards"),
)
#: Sections from the design that are not built yet (shown disabled, after the figures).
PLACEHOLDER_SECTIONS = ("Scoreboard & Players", "Batch & Parquet Export")


def page_url(name: str) -> QUrl:
    """The URL of a figure page with the replay's data folder attached."""
    return QUrl(f"gem://{scheme.HOST}/{name}.html?data={DATA_URL}")


class LoggingPage(QWebEnginePage):
    """A page that keeps the JavaScript errors it reports, so a broken figure is visible."""

    def __init__(self, profile: QWebEngineProfile | None, parent: QObject | None = None) -> None:
        if profile is not None:
            super().__init__(profile, parent)
        else:
            super().__init__(parent)
        self.errors: list[str] = []

    def javaScriptConsoleMessage(  # noqa: N802 (Qt override)
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        line: int,
        source: str,
    ) -> None:
        """Record errors (warnings and logs are ignored)."""
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(f"{message} ({source}:{line})")


class FigurePage(QObject):
    """One figure's web view and bridge.

    Attributes:
        name: The page name (``"fights"``, ``"objectives"``, ...).
        view: The web view to put in the window.
        bridge: The page's bridge (see ``bridge.py``).
        token: Which replay the page last loaded, or None if it never has.
    """

    def __init__(
        self, name: str, profile: QWebEngineProfile | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.token: int | None = None
        self.view = QWebEngineView()
        self.page = LoggingPage(profile, self.view)
        self.view.setPage(self.page)
        self.bridge = Bridge(self)
        self.channel = QWebChannel(self)
        self.channel.registerObject("gem", self.bridge)
        self.page.setWebChannel(self.channel)

    @property
    def errors(self) -> list[str]:
        """JavaScript errors the page has reported."""
        return self.page.errors

    def load(self, token: int) -> None:
        """Load the page for the replay identified by ``token``.

        Args:
            token: Changes whenever a different replay is opened.
        """
        self.token = token
        self.page.errors.clear()
        self.bridge.reset()  # the page connects again when it has loaded
        self.view.load(page_url(self.name))
