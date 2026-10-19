"""The Dashboard-Gem screen: roster rail, facts strip, the figure, and the telemetry drawer.

Layout (Material Telemetry Dark, from the Stitch design)::

    ┌ rail 256 px ┬ facts strip ─────────────────────────┐
    │ Radiant     │ web view: the fights figure          │
    │ Dire        │                                      │
    ├─────────────┴──────────────────────────────────────┤
    │ ▲ Analytical Telemetry  (drawer: chart + tables)   │
    └────────────────────────────────────────────────────┘

Everything shown is a fact the match records. The drawer reads ``dashboard.json`` and
``fights/index.json`` from the replay's figure data folder, so this view never loads the
whole parsed match.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QMargins, QPropertyAnimation, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gemstudio import paths, theme
from gemstudio.loading import format_elapsed
from gemstudio.models import RAW_ROLE, ROW_ROLE, Column, RowsModel, kilo, thousands
from gemstudio.transport import TransportBar

RAIL_WIDTH = 256
DRAWER_BAR = 40
DRAWER_BODY = 280
TEAM_COLOR = {"radiant": theme.RADIANT, "dire": theme.DIRE}


def hero_icon(short: str) -> QIcon | None:
    """The hero's icon from the bundled set, or None when there is none."""
    file = paths.hero_icons() / f"{short}.png"
    return QIcon(str(file)) if short and file.is_file() else None


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _clear(layout: QLayout) -> None:
    """Remove and delete everything in a layout, including widgets in nested layouts."""
    while (item := layout.takeAt(0)) is not None:
        if (widget := item.widget()) is not None:
            widget.deleteLater()
        elif (child := item.layout()) is not None:
            _clear(child)


def _label(text: str, name: str = "", *, tone: str | None = None) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    if tone:
        label.setProperty("team", tone)
    return label


# -- the roster rail ----------------------------------------------------------------------


class RosterRail(QWidget):
    """Each side's players: hero, player name, K/D/A and net worth.

    Signals:
        hero_picked(str): The hero name of a clicked player (for the figure to follow).
    """

    hero_picked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("rail")
        self.setFixedWidth(RAIL_WIDTH)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(10, 12, 10, 12)
        self._outer.setSpacing(6)
        self._buttons: list[QPushButton] = []
        self._outer.addStretch()

    def load(self, players: list[dict[str, Any]], net_worth: dict[str, int]) -> None:
        """Show the players, grouped by side.

        Args:
            players: The dashboard's players, Radiant first.
            net_worth: Each side's total net worth.
        """
        _clear(self._outer)
        self._buttons = []
        lead = net_worth.get("radiant", 0) - net_worth.get("dire", 0)
        for team in ("radiant", "dire"):
            ahead = lead if team == "radiant" else -lead
            header = QHBoxLayout()
            header.addWidget(_label(team.capitalize(), "teamHeader", tone=team))
            header.addStretch()
            header.addWidget(_label(f"{kilo(net_worth.get(team, 0))} net worth", "mono"))
            self._outer.addLayout(header)
            lead_text = (
                f"{'+' if ahead > 0 else ''}{kilo(ahead)} vs the other side" if ahead else ""
            )
            if lead_text:
                self._outer.addWidget(_label(lead_text, "mono"))
            for player in (p for p in players if p["team"] == team):
                self._outer.addWidget(self._row(player))
            self._outer.addSpacing(10)
        self._outer.addStretch()

    def _row(self, player: dict[str, Any]) -> QPushButton:
        button = QPushButton()
        button.setObjectName("player")
        button.setCheckable(True)
        button.setProperty("hero", player["hero"])
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(44)
        layout = QHBoxLayout(button)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)
        icon = QLabel()
        icon.setFixedSize(40, 24)
        pixmap = QPixmap(str(paths.hero_icons() / f"{player['icon']}.png"))
        if not pixmap.isNull():
            icon.setPixmap(
                pixmap.scaled(
                    40,
                    24,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(_label(player["hero"] or "Unknown hero", "step"))
        names.addWidget(_label(player["name"], "muted"))
        numbers = QVBoxLayout()
        numbers.setSpacing(0)
        kda = _label(f"{player['kills']}/{player['deaths']}/{player['assists']}", "monoStrong")
        kda.setAlignment(Qt.AlignmentFlag.AlignRight)
        worth = _label(kilo(player["net_worth"]), "mono")
        worth.setAlignment(Qt.AlignmentFlag.AlignRight)
        numbers.addWidget(kda)
        numbers.addWidget(worth)
        layout.addWidget(icon)
        layout.addLayout(names, 1)
        layout.addLayout(numbers)
        for child in button.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        button.clicked.connect(lambda _=False, b=button, h=player["hero"]: self._picked(b, h))
        self._buttons.append(button)
        return button

    def select_hero(self, hero: str) -> None:
        """Mark the player with this hero as followed, without announcing it.

        Used when the figure reports the user followed a hero there.

        Args:
            hero: The hero's display name.
        """
        for button in self._buttons:
            button.setChecked(button.property("hero") == hero)

    def _picked(self, button: QPushButton, hero: str) -> None:
        for other in self._buttons:
            other.setChecked(other is button and button.isChecked())
        if button.isChecked():
            self.hero_picked.emit(hero)


# -- the facts strip ----------------------------------------------------------------------


class FactsStrip(QWidget):
    """The match in one line: id, result, length, and counts the match records."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("facts")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 10, 16, 6)
        self._layout.setSpacing(8)

    def load(self, match: dict[str, Any]) -> None:
        """Show the match's facts.

        Args:
            match: The dashboard's ``match`` section.
        """
        _clear(self._layout)
        win = match.get("radiant_win")
        result = "" if win is None else f"{'Radiant' if win else 'Dire'} won "
        title = (
            f"Match {match['match_id']}  ·  {result}{match['radiant_score']}–{match['dire_score']}"
        )
        self._layout.addWidget(_label(title, "factTitle"))
        self._layout.addSpacing(8)
        facts = [
            f"Length {format_elapsed(match['duration_s'])}",
            f"Fights {match['fights']}",
            f"Roshan kills {match['roshan_kills']}",
            f"Towers destroyed {match['towers_destroyed']}",
            f"Wards placed {match['observers_placed'] + match['sentries_placed']}",
            f"Buybacks {match['buybacks']}",
        ]
        for fact in facts:
            self._layout.addWidget(_label(fact, "fact"))
        self._layout.addStretch()


# -- the telemetry drawer -----------------------------------------------------------------


class AdvantageChart(QChartView):
    """Radiant's gold and XP lead per minute: above zero Radiant is ahead, below Dire."""

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet(f"background: {theme.SURFACE}; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def load(self, advantage: dict[str, list[int]]) -> None:
        """Draw the lead curves.

        Args:
            advantage: ``{"minutes": [...], "gold": [...], "xp": [...]}``.
        """
        chart = QChart()
        chart.setBackgroundBrush(QBrush(QColor(theme.SURFACE)))
        chart.setBackgroundRoundness(0)
        chart.setMargins(QMargins(8, 4, 12, 4))
        chart.legend().setLabelColor(QColor(theme.TEXT_SECONDARY))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignTop)
        minutes = advantage["minutes"]
        values = []
        for name, key, color in (
            ("Gold lead", "gold", theme.PURE),
            ("XP lead", "xp", theme.SECONDARY),
        ):
            series = QLineSeries()
            series.setName(name)
            series.setPen(QPen(QColor(color), 2))
            for minute, value in zip(minutes, advantage[key], strict=False):
                series.append(minute, value / 1000)
                values.append(value / 1000)
            chart.addSeries(series)
        low, high = min(values + [0]), max(values + [0])
        pad = max((high - low) * 0.08, 0.5)
        x = QValueAxis()
        x.setRange(0, max(minutes[-1], 1) if minutes else 1)
        x.setLabelFormat("%d:00")
        x.setTickCount(min(len(minutes), 10) or 2)
        y = QValueAxis()
        y.setRange(low - pad, high + pad)
        y.setLabelFormat("%+.0fk")
        y.applyNiceNumbers()
        for axis in (x, y):
            axis.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis.setGridLineColor(QColor(theme.BORDER))
            axis.setLinePenColor(QColor(theme.BORDER_STRONG))
            axis.setLabelsFont(theme.mono_font(8))
        chart.addAxis(x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(y, Qt.AlignmentFlag.AlignLeft)
        for drawn in chart.series():
            drawn.attachAxis(x)
            drawn.attachAxis(y)
        self.setChart(chart)


def _team_color(row: dict[str, Any]) -> str:
    return TEAM_COLOR[row["team"]]


def _player_columns() -> list[Column]:
    return [
        Column(
            "hero",
            "Hero",
            "left",
            color=_team_color,
            width=150,
            icon=lambda row: hero_icon(row["icon"]),
        ),
        Column("name", "Player", "left", width=130),
        Column("level", "Lv", width=44),
        Column("kills", "K", width=44),
        Column("deaths", "D", width=44),
        Column("assists", "A", width=44),
        Column("last_hits", "LH", width=56),
        Column("denies", "DN", width=50),
        Column("gpm", "GPM", width=60),
        Column("xpm", "XPM", width=60),
        Column("net_worth", "Net worth", fmt=thousands, width=90),
        Column("hero_damage", "Hero dmg", fmt=thousands, width=90),
        Column("tower_damage", "Tower dmg", fmt=thousands, width=90),
        Column("hero_healing", "Healing", fmt=thousands, width=80),
    ]


def _fight_columns() -> list[Column]:
    def side_color(row: dict[str, Any]) -> str | None:
        return {"r": theme.RADIANT, "d": theme.DIRE}.get(row["more"])

    return [
        Column("n", "#", width=44),
        Column("start", "Time", "left", width=70),
        Column("score", "Kills R–D", "left", color=side_color, width=90),
        Column("deaths", "Deaths", width=70),
        Column("gold_r", "Gold R", fmt=lambda v: f"{v:+,}", width=84),
        Column("gold_d", "Gold D", fmt=lambda v: f"{v:+,}", width=84),
        Column("next", "Next", "left", width=260),
    ]


def _fight_rows(index: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for fight in index.get("fights", []):
        nxt = fight.get("next")
        side = {"r": "Radiant", "d": "Dire"}.get(nxt[1], "") if nxt else ""
        rows.append(
            {
                "n": fight["n"],
                "start": fight["start"],
                "score": f"{fight['kills'][0]}–{fight['kills'][1]}",
                "more": fight["more"],
                "deaths": fight["deaths"],
                "gold_r": fight["gold"][0],
                "gold_d": fight["gold"][1],
                "next": f"{nxt[0]} ({side}, {nxt[2]:.0f} s after)" if nxt else "",
            }
        )
    return rows


def _table(model: RowsModel) -> tuple[QTableView, QSortFilterProxyModel]:
    proxy = QSortFilterProxyModel()
    proxy.setSourceModel(model)
    proxy.setSortRole(RAW_ROLE)
    view = QTableView()
    view.setModel(proxy)
    view.setSortingEnabled(True)
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setShowGrid(False)
    view.setWordWrap(False)
    view.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)  # source order first
    view.verticalHeader().hide()
    view.verticalHeader().setDefaultSectionSize(30)
    view.horizontalHeader().setStretchLastSection(True)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    for i, column in enumerate(model.columns):
        view.setColumnWidth(i, column.width)
    return view, proxy


class TelemetryDrawer(QWidget):
    """The "Analytical Telemetry" drawer: a 40 px bar that expands to charts and tables.

    Signals:
        fight_picked(int): A fight row was selected (its number).
    """

    fight_picked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.body = QWidget()
        self.body.setObjectName("drawerBody")
        self.body.setMaximumHeight(0)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(8, 0, 8, 8)
        self.chart = AdvantageChart()
        self.players_model = RowsModel(_player_columns())
        self.players_view, _ = _table(self.players_model)
        self.fights_model = RowsModel(_fight_columns())
        self.fights_view, self.fights_proxy = _table(self.fights_model)
        self.fights_view.selectionModel().currentRowChanged.connect(self._fight_row)
        tabs = QTabWidget()
        tabs.addTab(self.chart, "Gold && XP advantage")  # && shows one &
        tabs.addTab(self.players_view, "Players")
        tabs.addTab(self.fights_view, "Fights")
        body_layout.addWidget(tabs)
        self.tabs = tabs

        bar = QWidget()
        bar.setObjectName("drawerBar")
        bar.setFixedHeight(DRAWER_BAR)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(8, 0, 12, 0)
        self.toggle = QPushButton("▲  Analytical Telemetry")
        self.toggle.setObjectName("drawerToggle")
        self.toggle.setCheckable(True)
        self.toggle.setToolTip("Show or hide the charts and tables")
        self.toggle.toggled.connect(self.set_open)
        self.hint = _label("Above zero Radiant is ahead, below zero Dire", "mono")
        self.hint.hide()
        bar_layout.addWidget(self.toggle)
        bar_layout.addStretch()
        bar_layout.addWidget(self.hint)

        outer.addWidget(self.body)
        outer.addWidget(bar)
        self._syncing = False  # True while the table is changed to follow the figure
        self._animation = QPropertyAnimation(self.body, b"maximumHeight", self)
        self._animation.setDuration(160)

    def load(self, data: dict[str, Any], fights_index: dict[str, Any]) -> None:
        """Fill the chart and tables.

        Args:
            data: The dashboard data (``dashboard.json``).
            fights_index: The fights figure's index (``fights/index.json``).
        """
        self.chart.load(data["advantage"])
        self.players_model.set_rows(data["players"])
        self.fights_model.set_rows(_fight_rows(fights_index))

    def set_open(self, opened: bool) -> None:
        """Expand or collapse the drawer."""
        self.toggle.setText(("▼" if opened else "▲") + "  Analytical Telemetry")
        self.hint.setVisible(opened)
        self._animation.stop()
        self._animation.setStartValue(self.body.maximumHeight())
        self._animation.setEndValue(DRAWER_BODY if opened else 0)
        self._animation.start()
        if self.toggle.isChecked() != opened:
            self.toggle.setChecked(opened)

    def select_fight(self, number: int) -> bool:
        """Select the row of fight ``number`` without announcing it.

        Used when the figure reports the user picked a fight there.

        Args:
            number: The fight's number.

        Returns:
            Whether the table has that fight.
        """
        proxy = self.fights_proxy
        for r in range(proxy.rowCount()):
            row = proxy.data(proxy.index(r, 0), ROW_ROLE)
            if row and row["n"] == number:
                self._syncing = True
                try:
                    self.fights_view.selectRow(r)
                    self.fights_view.scrollTo(proxy.index(r, 0))
                finally:
                    self._syncing = False
                return True
        return False

    def _fight_row(self, current: Any, _previous: Any) -> None:
        if current.isValid() and not self._syncing:
            row = self.fights_proxy.data(current, ROW_ROLE)
            if row:
                self.fight_picked.emit(int(row["n"]))


# -- the screen ---------------------------------------------------------------------------


class DashboardView(QWidget):
    """Rail, facts strip, the figure's web view, and the telemetry drawer.

    Signals:
        hero_picked(str): A roster player was clicked (hero name).
        fight_picked(int): A row of the fights table was selected.
    """

    hero_picked = Signal(str)
    fight_picked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("canvas")
        self.rail = RosterRail()
        self.facts = FactsStrip()
        self.transport = TransportBar()
        self.drawer = TelemetryDrawer()
        self.rail.hero_picked.connect(self.hero_picked)
        self.drawer.fight_picked.connect(self.fight_picked)

        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(0)
        center.addWidget(self.facts)
        center.addWidget(self.transport)
        # One page per figure tab, added as the tabs are first shown.
        self.pages = QStackedWidget()
        self._page_widgets: dict[str, QWidget] = {}
        center.addWidget(self.pages, 1)
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.rail)
        scroll.setFixedWidth(RAIL_WIDTH + 12)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        middle.addWidget(scroll)
        middle.addLayout(center, 1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(middle, 1)
        outer.addWidget(self.drawer)

    def add_page(self, name: str, widget: QWidget) -> None:
        """Add a figure page (a web view) under ``name``."""
        self._page_widgets[name] = widget
        self.pages.addWidget(widget)

    def show_page(self, name: str) -> None:
        """Show a figure page; the playback controls belong to the Fights page only."""
        self.pages.setCurrentWidget(self._page_widgets[name])
        self.transport.setVisible(name == "fights")

    def load(self, data_dir: Path) -> None:
        """Read a replay's figure data folder and fill the screen.

        Args:
            data_dir: The folder holding ``dashboard.json`` and ``fights/index.json``.

        Raises:
            FileNotFoundError: If the dashboard data is missing.
        """
        data = json.loads((data_dir / "dashboard.json").read_text(encoding="utf-8"))
        index_file = data_dir / "fights" / "index.json"
        index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.is_file() else {}
        self.rail.load(data["players"], data["match"]["net_worth"])
        self.facts.load(data["match"])
        self.drawer.load(data, index)
