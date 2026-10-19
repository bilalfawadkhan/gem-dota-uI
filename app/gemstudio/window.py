"""The main window: open a replay, watch it load, then work in the dashboard.

Pages (one is shown at a time): the empty state, the loading view while a replay is read,
and the dashboard (roster rail, the fights figure in a web view, telemetry drawer). The web
view reads the opened replay's own figure data from ``gem://app/_data/`` (see ``export.py``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from gemstudio import __version__, paths, scheme
from gemstudio.dashboard import DashboardView
from gemstudio.figures import FIGURE_PAGES, PLACEHOLDER_SECTIONS, FigurePage
from gemstudio.jobs import ParseJob
from gemstudio.loading import LoadingView
from gemstudio.precheck import ReplayFileError, check_replay_file
from gemstudio.transport import Playback


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class TopBar(QWidget):
    """The 48 px bar: brand, the open replay, status, and Open."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("topbar")
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)
        brand = QLabel("gem")
        brand.setObjectName("brand")
        sub = QLabel("Studio")
        sub.setObjectName("brandSub")
        self.engine = QLabel(f"app {__version__}")
        self.engine.setObjectName("chip")
        self.engine.setFixedHeight(24)
        self.replay = QLabel("")
        self.replay.setObjectName("muted")
        self.status = QLabel("Ready")
        self.status.setObjectName("chip")
        self.status.setFixedHeight(24)
        self.open_button = QPushButton("Open replay…")
        self.open_button.setObjectName("primary")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        for widget in (brand, sub, self.engine):
            layout.addWidget(widget)
        layout.addSpacing(8)
        layout.addWidget(self.replay)
        layout.addStretch()
        layout.addWidget(self.status)
        layout.addWidget(self.open_button)

    def set_status(self, text: str, tone: str = "") -> None:
        """Show a status chip; ``tone`` is ``"ok"``, ``"warn"``, ``"busy"`` or empty."""
        self.status.setText(text)
        self.status.setProperty("tone", tone)
        _repolish(self.status)


class EmptyView(QWidget):
    """Shown before a replay is open."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("canvas")
        layout = QVBoxLayout(self)
        layout.addStretch()
        title = QLabel("Open a Dota 2 replay")
        title.setObjectName("loadTitle")
        hint = QLabel("Choose a .dem file, or drop one anywhere in this window.")
        hint.setObjectName("muted")
        self.button = QPushButton("Open replay…")
        self.button.setObjectName("primary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        for widget in (title, hint, self.button):
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()


class MainWindow(QMainWindow):
    """Replay viewer: top bar, section tabs, and the empty / loading / dashboard pages."""

    def __init__(
        self,
        web_dir: Path | None = None,
        cache_root: Path | None = None,
        profile: QWebEngineProfile | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"Gem Studio {__version__}")
        self.setMinimumSize(1100, 680)
        self.resize(1440, 900)
        self.setAcceptDrops(True)

        self.job = ParseJob(self, cache_root)
        self.job.phase.connect(self._on_phase)
        self.job.steps.connect(self._on_steps)
        self.job.finished.connect(self._on_finished)
        self.job.failed.connect(self._on_failed)
        self.job.cancelled.connect(self._on_cancelled)

        self.handler = scheme.GemSchemeHandler(
            web_dir or paths.web_dist(), paths.demo_data_roots(), self
        )
        # One web view per figure tab (see figures.py); the Fights page is the first tab
        # and the one the native widgets talk to. The others are created when first shown.
        self._profile = profile if profile is not None else QWebEngineProfile.defaultProfile()
        scheme.install(self._profile, self.handler)
        self.pages: dict[str, FigurePage] = {}
        self._token = 0  # changes when a different replay is opened; stale pages reload
        fights = self._make_page("fights")
        self.view = fights.view
        self.bridge = fights.bridge

        self.last_summary: dict | None = None
        # Errors always go to `errors`; they are also shown in a dialog unless this is False
        # (the self-test turns dialogs off: nobody is there to close one).
        self.interactive = True
        self.errors: list[dict] = []
        self._loaded = False  # a replay is on show in the dashboard
        self._build_ui()

    # -- construction -------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.open_action = QAction("&Open replay…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_replay)
        self.cancel_action = QAction("&Cancel reading", self)
        self.cancel_action.setEnabled(False)
        self.cancel_action.triggered.connect(self.job.cancel)
        self.telemetry_action = QAction("Analytical &Telemetry", self)
        self.telemetry_action.setCheckable(True)
        self.telemetry_action.setShortcut("Ctrl+T")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addActions([self.open_action, self.cancel_action])
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
        self.menuBar().addMenu("&View").addAction(self.telemetry_action)

        self.topbar = TopBar()
        self.topbar.open_button.clicked.connect(self.choose_replay)

        self.sections = QTabBar()
        self.sections.setObjectName("sections")
        self.sections.setExpanding(False)
        self.sections.setDrawBase(False)
        for spec in FIGURE_PAGES:
            self.sections.addTab(spec.title.replace("&", "&&"))  # a single & would mark a shortcut
        for title in PLACEHOLDER_SECTIONS:
            index = self.sections.addTab(title.replace("&", "&&"))
            self.sections.setTabEnabled(index, False)
            self.sections.setTabToolTip(index, "Coming in a later phase")
        self.sections.currentChanged.connect(self._on_tab)
        bar = QWidget()
        bar.setObjectName("sectionsBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(8, 0, 8, 0)
        bar_layout.addWidget(self.sections)
        bar_layout.addStretch()

        self.banner = QLabel("")
        self.banner.setObjectName("banner")
        self.banner.hide()

        self.empty = EmptyView()
        self.empty.button.clicked.connect(self.choose_replay)
        self.loading = LoadingView()
        self.loading.cancel_requested.connect(self.job.cancel)
        self.dashboard = DashboardView()
        self.dashboard.add_page("fights", self.view)
        # Native table / roster -> figure, and figure -> native table / roster.
        self.dashboard.fight_picked.connect(self.bridge.request_fight)
        self.dashboard.hero_picked.connect(self.bridge.request_hero)
        self.bridge.fight_selected.connect(self.dashboard.drawer.select_fight)
        self.bridge.hero_followed.connect(self.dashboard.rail.select_hero)
        # Native playback controls <-> the figure's player.
        transport = self.dashboard.transport
        transport.play_requested.connect(self.bridge.request_playing)
        transport.seek_requested.connect(self.bridge.request_seek)
        transport.speed_requested.connect(self.bridge.request_speed)
        self.bridge.playback_changed.connect(self._on_playback)
        self.addActions(transport.actions_with_shortcuts)
        self.telemetry_action.toggled.connect(self.dashboard.drawer.set_open)
        self.dashboard.drawer.toggle.toggled.connect(self.telemetry_action.setChecked)

        self.stack = QStackedWidget()
        for page in (self.empty, self.loading, self.dashboard):
            self.stack.addWidget(page)

        central = QWidget()
        central.setObjectName("canvas")
        column = QVBoxLayout(central)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        for widget in (self.topbar, bar, self.banner):
            column.addWidget(widget)
        column.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    # -- opening a replay ---------------------------------------------------------------

    def choose_replay(self) -> None:
        """Ask for a replay file and open it."""
        name, _ = QFileDialog.getOpenFileName(self, "Open replay", "", "Dota 2 replays (*.dem)")
        if name:
            self.open_replay(name)

    def open_replay(self, path: str | Path) -> None:
        """Check a replay file and start reading it.

        Args:
            path: The chosen file. A wrong file is refused with a message, not parsed.
        """
        if self.job.running:
            QMessageBox.information(self, "Gem Studio", "A replay is already being read.")
            return
        try:
            file = check_replay_file(path)
        except ReplayFileError as exc:
            self.errors.append({"kind": "file", "message": str(exc)})
            if self.interactive:
                QMessageBox.warning(self, "Cannot open replay", str(exc))
            return
        self.setWindowTitle(f"{file.name} - Gem Studio {__version__}")
        self.topbar.replay.setText(file.name)
        self.banner.hide()
        self._set_busy(True)
        self.loading.begin(file.name, file.stat().st_size / 2**20)
        self.stack.setCurrentWidget(self.loading)
        self.job.start(file)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (Qt override)
        """Accept a dragged .dem file."""
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (Qt override)
        """Open a dropped file."""
        self.open_replay(event.mimeData().urls()[0].toLocalFile())

    # -- job callbacks ------------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self.cancel_action.setEnabled(busy)
        self.open_action.setEnabled(not busy)
        self.topbar.open_button.setEnabled(not busy)
        if busy:
            self.topbar.set_status("Reading…", "busy")

    def _on_phase(self, label: str) -> None:
        self.topbar.status.setToolTip(label)

    def _on_steps(self, states: dict) -> None:
        self.loading.set_states(states)

    def _on_finished(self, summary: dict) -> None:
        self.last_summary = summary
        self.loading.end()
        self._set_busy(False)
        data_dir = Path(summary["data_dir"])
        self.handler.set_data_roots([data_dir])
        try:
            self.dashboard.load(data_dir)
        except (OSError, ValueError, KeyError) as exc:
            self._back_to_previous()
            self.errors.append({"kind": "dashboard", "message": str(exc)})
            if self.interactive:
                QMessageBox.warning(
                    self, "Cannot show the replay", f"Its dashboard data is unreadable: {exc}"
                )
            return
        self._loaded = True
        self._token += 1  # figures already created reload for this replay when shown
        where = "from saved results" if summary.get("cached") else "read"
        self.topbar.set_status(f"Match {summary['match_id']} {where}", "ok")
        if summary.get("parse_error"):
            self.banner.setText(
                f"This replay is incomplete: it stops at tick {summary.get('truncated_at_tick')}. "
                "Showing what could be read."
            )
            self.banner.show()
            self.topbar.set_status("Incomplete replay", "warn")
        self.show_figure()

    def _back_to_previous(self) -> None:
        self.loading.end()
        self._set_busy(False)
        self.stack.setCurrentWidget(self.dashboard if self._loaded else self.empty)
        self.topbar.set_status("Ready")

    def _on_failed(self, error: dict) -> None:
        self._back_to_previous()
        self.topbar.set_status("Could not read the replay", "warn")
        self.errors.append(error)
        if not self.interactive:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        kind = error.get("kind")
        if kind == "replay":
            box.setWindowTitle("Cannot read replay")
            box.setText(
                "This replay could not be decoded. It may be damaged or from an "
                "unsupported game version."
            )
        elif kind == "export":
            box.setWindowTitle("Cannot prepare the figures")
            box.setText("The replay was read, but its figures could not be prepared.")
        else:
            box.setWindowTitle("Gem Studio hit a problem")
            box.setText(
                "Something went wrong while reading the replay. Details were saved to the log."
            )
        box.setDetailedText(error.get("traceback") or error.get("message", ""))
        box.exec()

    def _on_cancelled(self) -> None:
        self._back_to_previous()
        self.topbar.set_status("Cancelled")

    # -- the figure ---------------------------------------------------------------------

    def show_figure(self) -> None:
        """Show the dashboard on the first tab (the Fights figure)."""
        self.sections.blockSignals(True)
        self.sections.setCurrentIndex(0)
        self.sections.blockSignals(False)
        self._show_page("fights")

    def _make_page(self, name: str) -> FigurePage:
        page = FigurePage(name, self._profile, self)
        self.pages[name] = page
        # A link in any figure that points at a fight opens it in the Fights tab.
        page.bridge.fight_requested.connect(self._open_fight)
        return page

    def _page(self, name: str) -> FigurePage:
        """The figure page for ``name``, created (and added to the dashboard) on first use."""
        if name not in self.pages:
            page = self._make_page(name)
            self.dashboard.add_page(name, page.view)
        return self.pages[name]

    def _show_page(self, name: str) -> None:
        page = self._page(name)
        if page.token != self._token:  # never loaded, or loaded for an earlier replay
            if name == "fights":
                self.dashboard.transport.set_state(None)  # until the new player reports
            page.load(self._token)
        self.dashboard.show_page(name)
        self.stack.setCurrentWidget(self.dashboard)

    def _on_tab(self, index: int) -> None:
        # While the empty or loading page is up, the tab only changes the selection; the page
        # for it appears when the replay is ready.
        if self.stack.currentWidget() is self.dashboard and 0 <= index < len(FIGURE_PAGES):
            self._show_page(FIGURE_PAGES[index].name)

    def _open_fight(self, number: int) -> None:
        """Open a fight in the Fights tab (from a link in another figure)."""
        self.sections.setCurrentIndex(0)
        self.bridge.request_fight(number)

    def _on_playback(
        self,
        available: bool,
        playing: bool,
        clock: str,
        seconds: float,
        duration: float,
        speed: float,
    ) -> None:
        state = Playback(playing, clock, seconds, duration, speed) if available else None
        self.dashboard.transport.set_state(state)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        """Stop a running job before the window closes."""
        self.job.cancel()
        super().closeEvent(event)
