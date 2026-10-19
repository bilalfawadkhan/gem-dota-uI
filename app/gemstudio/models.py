"""A small table model over rows of plain dicts (no pandas: the UI process never imports it)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor, QIcon

Index = QModelIndex | QPersistentModelIndex
_ROOT = QModelIndex()  # the default parent: top level

#: Role for the raw (unformatted) value, which sorting uses.
RAW_ROLE = Qt.ItemDataRole.UserRole + 1
#: Role for the whole row dict.
ROW_ROLE = Qt.ItemDataRole.UserRole + 2


@dataclass(frozen=True)
class Column:
    """One table column.

    Attributes:
        key: The row dict's key.
        title: The header text.
        align: ``"left"`` or ``"right"`` (numbers right-align).
        fmt: Turns the raw value into display text; default ``str``.
        color: Returns a colour name for a row, or None for the default.
        icon: Returns an icon for a row, shown beside the text.
        width: Preferred width in pixels.
    """

    key: str
    title: str
    align: str = "right"
    fmt: Callable[[Any], str] | None = None
    color: Callable[[dict[str, Any]], str | None] | None = None
    icon: Callable[[dict[str, Any]], QIcon | None] | None = None
    width: int = 70


def thousands(value: Any) -> str:
    """``12345`` -> ``"12,345"``; missing values show a dash."""
    return "-" if value is None else f"{int(value):,}"


def kilo(value: Any) -> str:
    """``27720`` -> ``"27.7k"``."""
    return "-" if value is None else f"{value / 1000:.1f}k"


def clock(seconds: Any) -> str:
    """``2159`` -> ``"35:59"``."""
    if seconds is None:
        return "-"
    seconds = int(seconds)
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    return f"{sign}{seconds // 60}:{seconds % 60:02d}"


class RowsModel(QAbstractTableModel):
    """Rows of dicts shown through column specs; sort with a ``QSortFilterProxyModel`` on ``RAW_ROLE``."""

    def __init__(self, columns: list[Column], rows: list[dict[str, Any]] | None = None):
        super().__init__()
        self.columns = columns
        self.rows: list[dict[str, Any]] = rows or []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        """Replace all rows."""
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent: Index = _ROOT) -> int:  # noqa: N802 (Qt override)
        """Number of rows."""
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: Index = _ROOT) -> int:  # noqa: N802 (Qt override)
        """Number of columns."""
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Display text, alignment, colour, icon, raw value or row, by role."""
        if not index.isValid():
            return None
        column, row = self.columns[index.column()], self.rows[index.row()]
        value = row.get(column.key)
        if role == Qt.ItemDataRole.DisplayRole:
            return column.fmt(value) if column.fmt else ("" if value is None else str(value))
        if role == Qt.ItemDataRole.TextAlignmentRole:
            side = (
                Qt.AlignmentFlag.AlignRight
                if column.align == "right"
                else Qt.AlignmentFlag.AlignLeft
            )
            return int(side | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and column.color:
            name = column.color(row)
            return QColor(name) if name else None
        if role == Qt.ItemDataRole.DecorationRole and column.icon:
            return column.icon(row)
        if role == RAW_ROLE:
            return value
        if role == ROW_ROLE:
            return row
        return None

    def headerData(  # noqa: N802 (Qt override)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Column titles."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section].title
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.TextAlignmentRole:
            side = (
                Qt.AlignmentFlag.AlignRight
                if self.columns[section].align == "right"
                else Qt.AlignmentFlag.AlignLeft
            )
            return int(side | Qt.AlignmentFlag.AlignVCenter)
        return None
