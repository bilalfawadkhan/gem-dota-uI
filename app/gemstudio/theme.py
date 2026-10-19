"""The app's look: Material Telemetry Dark, from the Stitch design (Dashboard-Gem).

Tokens come from ``app/design/dashboard-gem/README.md``. Fonts: the design uses Roboto Flex
and JetBrains Mono; neither ships with Windows, so each token lists fallbacks and the first
installed family is used. (Bundling the fonts, both open licence, is a packaging task.)
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

# Surfaces (tonal layers; depth comes from lighter tiers, not shadows)
CANVAS = "#131314"  # level 0
SURFACE = "#1e1f20"  # level 1: cards, rails
CONTAINER = "#28292a"  # level 2: headers, inputs
CONTAINER_HIGH = "#333537"  # level 3
CONTAINER_HIGHEST = "#3c4043"  # level 4: menus
BORDER = "#3c4043"
BORDER_STRONG = "#5f6368"

# Text
TEXT = "#e8eaed"
TEXT_SECONDARY = "#9aa0a6"
TEXT_TERTIARY = "#80868b"

# Accents and data semantics
PRIMARY = "#8ab4f8"
PRIMARY_HOVER = "#a6c8ff"
ON_PRIMARY = "#131314"
SECONDARY = "#78d9ec"
RADIANT = "#81c995"
DIRE = "#f28b82"
PURE = "#fdd663"
MAGICAL = "#c58af9"

BODY_FONTS = ("Roboto Flex", "Roboto", "Segoe UI Variable Text", "Segoe UI", "Arial")
MONO_FONTS = ("JetBrains Mono", "Cascadia Mono", "Cascadia Code", "Consolas", "Courier New")


def _first_installed(candidates: tuple[str, ...]) -> str:
    installed = set(QFontDatabase.families())
    return next((name for name in candidates if name in installed), candidates[-1])


def body_family() -> str:
    """The first installed body font of the design's fallback chain."""
    return _first_installed(BODY_FONTS)


def mono_family() -> str:
    """The first installed monospace font of the design's fallback chain."""
    return _first_installed(MONO_FONTS)


def mono_font(point_size: int = 9, bold: bool = False) -> QFont:
    """A monospace font for numbers, clocks and ticks."""
    font = QFont(mono_family(), point_size)
    font.setBold(bold)
    return font


def stylesheet(body: str, mono: str) -> str:
    """The application stylesheet.

    Args:
        body: Body font family.
        mono: Monospace font family (table headers, chips).

    Returns:
        QSS for the whole app.
    """
    return f"""
* {{ font-family: "{body}"; font-size: 13px; color: {TEXT}; }}
QMainWindow, QDialog, QMessageBox {{ background: {CANVAS}; }}
QWidget#canvas {{ background: {CANVAS}; }}
QToolTip {{ background: {CONTAINER_HIGHEST}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
           padding: 4px 8px; }}

QMenuBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item {{ padding: 6px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {CONTAINER}; }}
QMenu {{ background: {CONTAINER_HIGHEST}; border: 1px solid {BORDER_STRONG}; padding: 4px; }}
QMenu::item {{ padding: 6px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background: {CONTAINER_HIGH}; }}
QMenu::item:disabled {{ color: {TEXT_TERTIARY}; }}

/* Top bar and tab bar */
QWidget#topbar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QLabel#brand {{ font-size: 15px; font-weight: 600; letter-spacing: 0.5px; }}
QLabel#brandSub {{ color: {TEXT_SECONDARY}; font-size: 12px; }}
QLabel#chip {{ background: {CONTAINER}; border: 1px solid {BORDER}; border-radius: 4px;
              padding: 2px 8px; font-family: "{mono}"; font-size: 11px; color: {TEXT_SECONDARY}; }}
QLabel#chip[tone="ok"] {{ color: {RADIANT}; }}
QLabel#chip[tone="warn"] {{ color: {PURE}; }}
QLabel#chip[tone="busy"] {{ color: {PRIMARY}; }}

QTabBar#sections {{ background: {SURFACE}; }}
QTabBar#sections::tab {{ background: transparent; color: {TEXT_SECONDARY}; padding: 10px 16px;
                         border-bottom: 2px solid transparent; font-weight: 500; }}
QTabBar#sections::tab:selected {{ color: {PRIMARY}; border-bottom: 2px solid {PRIMARY}; }}
QTabBar#sections::tab:hover:!selected {{ color: {TEXT}; background: {CONTAINER}; }}
QTabBar#sections::tab:disabled {{ color: {TEXT_TERTIARY}; }}
QWidget#sectionsBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}

/* Buttons */
QPushButton {{ background: {CONTAINER}; border: 1px solid {BORDER}; border-radius: 8px;
              padding: 6px 14px; color: {PRIMARY}; font-weight: 500; }}
QPushButton:hover {{ background: {CONTAINER_HIGH}; border-color: {BORDER_STRONG}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {TEXT_TERTIARY}; border-color: {BORDER}; }}
QPushButton#primary {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: 1px solid {PRIMARY}; }}
QPushButton#primary:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#primary:disabled {{ background: {CONTAINER}; color: {TEXT_TERTIARY}; border-color: {BORDER}; }}

/* Banner under the tab bar */
QLabel#banner {{ background: rgba(253, 214, 99, 0.10); color: {PURE};
                border-bottom: 1px solid rgba(253, 214, 99, 0.35); padding: 6px 16px; }}

/* Roster rail */
QWidget#rail {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QLabel#teamHeader {{ font-weight: 600; letter-spacing: 0.4px; }}
QLabel#teamHeader[team="radiant"] {{ color: {RADIANT}; }}
QLabel#teamHeader[team="dire"] {{ color: {DIRE}; }}
QLabel#mono {{ font-family: "{mono}"; font-size: 11px; color: {TEXT_SECONDARY}; }}
QLabel#monoStrong {{ font-family: "{mono}"; font-size: 12px; font-weight: 600; }}
QLabel#muted {{ color: {TEXT_SECONDARY}; font-size: 12px; }}
QPushButton#player {{ background: transparent; border: none; border-radius: 8px; padding: 4px 6px;
                     text-align: left; color: {TEXT}; }}
QPushButton#player:hover {{ background: {CONTAINER}; }}
QPushButton#player:checked {{ background: rgba(138, 180, 248, 0.12); }}

/* Facts strip */
QWidget#facts {{ background: {CANVAS}; }}
QLabel#factTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#fact {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px 10px;
              font-family: "{mono}"; font-size: 11px; color: {TEXT_SECONDARY}; }}

/* Telemetry drawer */
QWidget#drawerBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
QPushButton#drawerToggle {{ background: transparent; border: 1px solid transparent; color: {TEXT};
                           font-weight: 600; padding: 6px 12px; }}
QPushButton#drawerToggle:hover {{ background: {CONTAINER}; border-color: {BORDER}; }}
QPushButton#drawerToggle:checked {{ color: {PRIMARY}; }}
QWidget#drawerBody {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
QTabWidget::pane {{ border: none; background: {SURFACE}; }}
QTabWidget QTabBar::tab {{ background: transparent; color: {TEXT_SECONDARY}; padding: 8px 14px;
                          border-bottom: 2px solid transparent; }}
QTabWidget QTabBar::tab:selected {{ color: {PRIMARY}; border-bottom: 2px solid {PRIMARY}; }}
QTabWidget QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

/* Tables */
QTableView {{ background: {SURFACE}; alternate-background-color: #222324; gridline-color: transparent;
             border: none; selection-background-color: rgba(138, 180, 248, 0.22);
             selection-color: {TEXT}; font-family: "{mono}"; font-size: 12px; }}
QTableView::item {{ padding: 0 8px; border: none; }}
QHeaderView::section {{ background: {CONTAINER}; color: {TEXT_SECONDARY}; border: none;
                       border-bottom: 1px solid {BORDER}; padding: 6px 8px; height: 22px;
                       font-family: "{mono}"; font-size: 11px; font-weight: 500; }}
QTableCornerButton::section {{ background: {CONTAINER}; border: none; }}

/* Playback transport */
QWidget#transport {{ background: {CANVAS}; border-bottom: 1px solid {BORDER}; }}
QPushButton#transportButton {{ min-width: 52px; padding: 5px 10px; }}
QPushButton#transportPlay {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: 1px solid {PRIMARY};
                            min-width: 44px; padding: 5px 12px; font-weight: 700; }}
QPushButton#transportPlay:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#transportPlay:disabled, QPushButton#transportButton:disabled {{
    background: {CONTAINER}; color: {TEXT_TERTIARY}; border: 1px solid {BORDER}; }}
QPushButton#speedChip {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
                        padding: 3px 10px; color: {TEXT_SECONDARY}; font-family: "{mono}"; font-size: 11px; }}
QPushButton#speedChip:hover {{ border-color: {BORDER_STRONG}; }}
QPushButton#speedChip:checked {{ background: rgba(138, 180, 248, 0.15); border-color: {PRIMARY};
                                color: {PRIMARY}; }}
QPushButton#speedChip:disabled {{ color: {TEXT_TERTIARY}; }}
QSlider::groove:horizontal {{ background: {CONTAINER}; border: 1px solid {BORDER}; height: 6px;
                             border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {PRIMARY}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {PRIMARY}; width: 14px; height: 14px; margin: -5px 0;
                             border-radius: 7px; }}
QSlider::groove:horizontal:disabled {{ background: {SURFACE}; }}
QSlider::sub-page:horizontal:disabled {{ background: {BORDER_STRONG}; }}
QSlider::handle:horizontal:disabled {{ background: {BORDER_STRONG}; }}
QLabel#time {{ font-family: "{mono}"; font-size: 12px; color: {TEXT}; }}

/* Scroll bars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_TERTIARY}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; border-radius: 5px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Loading */
QProgressBar {{ background: {CONTAINER}; border: 1px solid {BORDER}; border-radius: 3px; height: 6px;
               text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 3px; }}
QLabel#loadTitle {{ font-size: 20px; font-weight: 600; }}
QLabel#step {{ font-size: 13px; }}
QLabel#step[state="waiting"] {{ color: {TEXT_TERTIARY}; }}
QLabel#step[state="running"] {{ color: {TEXT}; }}
QLabel#step[state="done"] {{ color: {TEXT_SECONDARY}; }}
QLabel#stepMark[state="waiting"] {{ color: {TEXT_TERTIARY}; }}
QLabel#stepMark[state="running"] {{ color: {PRIMARY}; }}
QLabel#stepMark[state="done"] {{ color: {RADIANT}; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
"""


def apply_theme(app: QApplication) -> None:
    """Style the application: Fusion with a dark palette, then the stylesheet."""
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, CANVAS),
        (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.Base, SURFACE),
        (QPalette.ColorRole.AlternateBase, CONTAINER),
        (QPalette.ColorRole.Text, TEXT),
        (QPalette.ColorRole.Button, CONTAINER),
        (QPalette.ColorRole.ButtonText, TEXT),
        (QPalette.ColorRole.ToolTipBase, CONTAINER_HIGHEST),
        (QPalette.ColorRole.ToolTipText, TEXT),
        (QPalette.ColorRole.Highlight, PRIMARY),
        (QPalette.ColorRole.HighlightedText, ON_PRIMARY),
        (QPalette.ColorRole.PlaceholderText, TEXT_TERTIARY),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet(body_family(), mono_family()))
