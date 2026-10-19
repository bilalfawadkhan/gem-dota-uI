"""The dashboard screen from a small, hand-made data folder (no replay needed)."""

import json

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from gemstudio.dashboard import DRAWER_BODY, DashboardView, hero_icon
from gemstudio.models import ROW_ROLE


def player(i, team, hero, kills, net_worth):
    return {
        "player_id": i, "name": f"p{i}", "hero": hero, "icon": hero.lower().replace(" ", "_"),
        "team": team, "level": 20, "kills": kills, "deaths": 2, "assists": 5, "last_hits": 100,
        "denies": 5, "net_worth": net_worth, "gpm": 500, "xpm": 600, "hero_damage": 9000,
        "tower_damage": 1000, "hero_healing": 0, "observers": 1, "sentries": 1, "buybacks": 0,
    }  # fmt: skip


PLAYERS = [
    player(0, "radiant", "Axe", 6, 20000),
    player(1, "radiant", "Lion", 2, 12000),
    player(2, "dire", "Sniper", 4, 15000),
    player(3, "dire", "Tiny", 1, 9000),
]


def write_data(folder, players=PLAYERS):
    (folder / "fights").mkdir(parents=True, exist_ok=True)
    nw = {t: sum(p["net_worth"] for p in players if p["team"] == t) for t in ("radiant", "dire")}
    data = {
        "match": {
            "match_id": 42, "radiant_win": True, "radiant_score": 3, "dire_score": 2,
            "duration_s": 1800, "net_worth": nw, "roshan_kills": 1, "towers_destroyed": 4,
            "barracks_destroyed": 0, "fights": 2, "wards": 6, "observers_placed": 2,
            "sentries_placed": 2, "buybacks": 1, "parse_error": None, "truncated_at_tick": None,
        },
        "players": players,
        "advantage": {"minutes": [0, 1, 2, 3], "gold": [0, 500, -300, 1200], "xp": [0, 100, 50, 900]},
    }  # fmt: skip
    (folder / "dashboard.json").write_text(json.dumps(data))
    index = {"fights": [
        {"n": 1, "start": "02:10", "kills": [1, 0], "more": "r", "deaths": 1, "gold": [300, -20], "next": None},
        {"n": 2, "start": "09:30", "kills": [1, 2], "more": "d", "deaths": 3, "gold": [-80, 400],
         "next": ["Radiant tier 1 top tower", "r", 12.0]},
    ]}  # fmt: skip
    (folder / "fights" / "index.json").write_text(json.dumps(index))


def make_view(qapp, tmp_path, players=PLAYERS):
    write_data(tmp_path, players)
    view = DashboardView()
    view.resize(1280, 720)
    view.load(tmp_path)
    return view


def wait_for(condition, ms=2000):
    for _ in range(ms // 20):
        if condition():
            return True
        QTest.qWait(20)
    return False


def test_roster_groups_players_by_side(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    assert len(view.rail._buttons) == 4
    headers = [w.text() for w in view.rail.findChildren(QLabel) if w.objectName() == "teamHeader"]
    assert headers == ["Radiant", "Dire"]
    texts = {w.text() for w in view.rail.findChildren(QLabel)}
    assert {"Axe", "6/2/5", "20.0k"} <= texts


def test_roster_net_worth_lead_is_the_difference_of_the_sides(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    texts = {w.text() for w in view.rail.findChildren(QLabel)}
    assert "+8.0k vs the other side" in texts and "-8.0k vs the other side" in texts


def test_loading_another_replay_replaces_the_roster(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    write_data(tmp_path, PLAYERS[:2])
    view.load(tmp_path)
    assert len(view.rail._buttons) == 2
    # Deleted widgets linger until the event loop runs; process them before counting.
    QTest.qWait(50)
    headers = [w for w in view.rail.findChildren(QLabel) if w.objectName() == "teamHeader"]
    assert len(headers) == 2
    assert view.drawer.players_model.rowCount() == 2


def test_facts_strip_states_the_match(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    texts = [w.text() for w in view.facts.findChildren(QLabel)]
    assert "Match 42  ·  Radiant won 3–2" in texts
    assert {"Length 30:00", "Fights 2", "Roshan kills 1", "Wards placed 4", "Buybacks 1"} <= set(
        texts
    )


def test_tables_keep_match_order_until_sorted(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    proxy = view.drawer.players_view.model()
    heroes = [proxy.data(proxy.index(r, 0)) for r in range(proxy.rowCount())]
    assert heroes == ["Axe", "Lion", "Sniper", "Tiny"]
    proxy.sort(10, Qt.SortOrder.DescendingOrder)  # net worth, as clicking its header does
    heroes = [proxy.data(proxy.index(r, 0)) for r in range(proxy.rowCount())]
    assert heroes == ["Axe", "Sniper", "Lion", "Tiny"]


def test_fights_table_shows_facts_and_what_came_next(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    model = view.drawer.fights_model
    rows = model.rows
    assert [r["score"] for r in rows] == ["1–0", "1–2"]
    assert (
        rows[0]["next"] == ""
        and rows[1]["next"] == "Radiant tier 1 top tower (Radiant, 12 s after)"
    )
    assert model.data(model.index(1, 4)) == "-80" and model.data(model.index(1, 5)) == "+400"


def test_drawer_opens_and_closes(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    drawer = view.drawer
    view.show()
    assert drawer.body.maximumHeight() == 0 and not drawer.toggle.isChecked()
    drawer.toggle.setChecked(True)
    assert wait_for(lambda: drawer.body.maximumHeight() == DRAWER_BODY)
    assert drawer.toggle.text().startswith("▼")
    drawer.toggle.setChecked(False)
    assert wait_for(lambda: drawer.body.maximumHeight() == 0)
    assert drawer.toggle.text().startswith("▲")


def test_picking_a_fight_row_emits_its_number(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    picked = []
    view.fight_picked.connect(picked.append)
    table = view.drawer.fights_view
    table.selectRow(1)
    assert picked == [2]


def test_clicking_a_player_emits_the_hero_name(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    picked = []
    view.hero_picked.connect(picked.append)
    view.rail._buttons[2].click()
    assert picked == ["Sniper"]
    view.rail._buttons[2].click()  # clicking again unselects; nothing to follow
    assert picked == ["Sniper"]


def test_the_chart_handles_a_match_with_no_curve(qapp, tmp_path):
    view = make_view(qapp, tmp_path)
    view.drawer.chart.load({"minutes": [], "gold": [], "xp": []})
    assert len(view.drawer.chart.chart().series()) == 2


def test_a_missing_icon_is_none_not_an_error(qapp):
    assert hero_icon("") is None and hero_icon("no_such_hero") is None


def test_the_roster_survives_an_empty_match(qapp, tmp_path):
    view = make_view(qapp, tmp_path, players=[])
    assert view.rail._buttons == [] and view.drawer.players_model.rowCount() == 0
    assert QModelIndex().isValid() is False
    assert view.drawer.fights_model.data(view.drawer.fights_model.index(0, 0), ROW_ROLE)["n"] == 1
