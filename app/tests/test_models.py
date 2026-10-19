from PySide6.QtCore import Qt

from gemstudio.models import RAW_ROLE, ROW_ROLE, Column, RowsModel, clock, kilo, thousands


def test_formatters():
    assert thousands(12345) == "12,345" and thousands(None) == "-"
    assert kilo(27720) == "27.7k" and kilo(-25300) == "-25.3k" and kilo(None) == "-"
    assert clock(2159) == "35:59" and clock(0) == "0:00" and clock(-90) == "-1:30"
    assert clock(None) == "-"


def make_model():
    columns = [
        Column("name", "Name", "left", color=lambda row: "#81c995" if row["win"] else None),
        Column("gold", "Gold", fmt=thousands),
    ]
    return RowsModel(
        columns,
        [{"name": "A", "gold": 1500, "win": True}, {"name": "B", "gold": None, "win": False}],
    )


def test_display_raw_row_and_headers():
    model = make_model()
    assert (model.rowCount(), model.columnCount()) == (2, 2)
    first, second = model.index(0, 1), model.index(1, 1)
    assert model.data(first, Qt.ItemDataRole.DisplayRole) == "1,500"
    assert model.data(second, Qt.ItemDataRole.DisplayRole) == "-"  # a missing value is a dash
    assert model.data(first, RAW_ROLE) == 1500 and model.data(second, RAW_ROLE) is None
    assert model.data(model.index(1, 0), ROW_ROLE)["name"] == "B"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "Gold"


def test_alignment_and_colour_follow_the_column():
    model = make_model()
    right = model.data(model.index(0, 1), Qt.ItemDataRole.TextAlignmentRole)
    left = model.data(model.index(0, 0), Qt.ItemDataRole.TextAlignmentRole)
    assert right & Qt.AlignmentFlag.AlignRight and left & Qt.AlignmentFlag.AlignLeft
    assert model.data(model.index(0, 0), Qt.ItemDataRole.ForegroundRole).name() == "#81c995"
    assert model.data(model.index(1, 0), Qt.ItemDataRole.ForegroundRole) is None


def test_set_rows_resets_the_model():
    model = make_model()
    model.set_rows([])
    assert model.rowCount() == 0
