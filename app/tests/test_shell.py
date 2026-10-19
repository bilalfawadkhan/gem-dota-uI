"""The Qt shell, run offscreen: the real window, web view, scheme handler and worker processes."""

import json
import time
from pathlib import Path

import pytest

from gemstudio import paths

pytestmark = pytest.mark.gui

if not (paths.web_dist() / "fights.html").is_file():
    pytest.skip("build the figures first: cd app/web && npm run build", allow_module_level=True)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWebEngineCore import QWebEngineProfile  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from gemstudio import scheme  # noqa: E402
from gemstudio.models import ROW_ROLE  # noqa: E402
from gemstudio.transport import PAUSE, PLAY  # noqa: E402
from gemstudio.window import MainWindow  # noqa: E402

scheme.register_scheme()  # before the QApplication exists


@pytest.fixture
def window(qapp, tmp_path):
    profile = QWebEngineProfile()  # off the record; one per window
    win = MainWindow(cache_root=tmp_path / "cache", profile=profile)
    win.show()
    yield win
    win.close()
    win.deleteLater()
    QTest.qWait(50)
    del profile


def wait_until(condition, timeout_s=30.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        QTest.qWait(50)
    return False


def js(window, script, timeout_s=10.0):
    """Run JavaScript in the page and return its result."""
    box = []
    window.view.page().runJavaScript(script, box.append)
    assert wait_until(lambda: box, timeout_s), f"no result for {script}"
    return box[0]


def test_starts_on_the_empty_page(window):
    assert window.stack.currentWidget() is window.empty
    assert window.sections.tabText(0) == "Fight Replay && Dashboard"  # && is one & on screen
    assert not window.banner.isVisible()


def test_figure_loads_over_the_gem_scheme(window):
    window.show_figure()
    assert window.stack.currentWidget() is window.dashboard
    count = "document.querySelectorAll('.fights-fig-list [data-fight]').length"
    assert wait_until(lambda: (js(window, count) or 0) > 0), "fights list never rendered"
    assert js(window, count) == 36  # the committed demo data (no replay open)
    assert js(window, "document.querySelectorAll('[data-fights] [data-fight]').length") > 0
    assert js(window, "typeof window.gemFigure.selectFight") == "function"
    assert wait_until(lambda: js(window, "document.querySelectorAll('[data-scrub]').length") == 1)


def test_reading_shows_loading_then_the_dashboard(window, fixture_dem):
    ticks = []
    ticker = QTimer()
    ticker.setInterval(20)
    ticker.timeout.connect(lambda: ticks.append(time.monotonic()))
    ticker.start()

    states, finished = [], []
    window.job.steps.connect(states.append)
    window.job.finished.connect(finished.append)
    window.open_replay(fixture_dem)

    # While the job runs: the loading page, the busy state, and no way to start a second one.
    assert window.job.running
    assert window.stack.currentWidget() is window.loading
    assert window.topbar.status.text() == "Reading…"
    assert not window.open_action.isEnabled() and window.cancel_action.isEnabled()
    assert not window.topbar.open_button.isEnabled()
    assert window.loading.subtitle.text().startswith(fixture_dem.name)

    assert wait_until(lambda: finished, 120)
    ticker.stop()

    summary = finished[0]
    assert summary["players"] == 10 and summary["parse_error"]
    # The UI thread kept running during the read (a blocked thread ticks about 0 times).
    assert len(ticks) > 20
    # Every step was reported, and all four ended done.
    assert states and states[-1] == {
        "parse": "done",
        "states": "done",
        "places": "done",
        "export": "done",
    }
    seen = {name for snapshot in states for name, value in snapshot.items() if value == "running"}
    assert seen == {"parse", "states", "places", "export"}

    assert window.stack.currentWidget() is window.dashboard
    assert window.banner.isVisible() and "incomplete" in window.banner.text()
    assert window.topbar.status.text() == "Incomplete replay"
    assert window.open_action.isEnabled() and not window.cancel_action.isEnabled()
    assert Path(summary["data_dir"]).joinpath("dashboard.json").is_file()
    # The figure loads this replay's own data; the truncated fixture has no fights, and
    # the committed demo data would list 36.
    side = "document.querySelector('[data-side]')?.textContent ?? ''"
    assert wait_until(lambda: "No fights here" in (js(window, side) or ""))
    assert js(window, "document.querySelectorAll('.fights-fig-list [data-fight]').length") == 0
    # With no fight there is no player: the playback controls stay disabled.
    assert (
        window.dashboard.transport.state is None and not window.dashboard.transport.play.isEnabled()
    )


def test_cancel_returns_to_the_page_before(window, fixture_dem):
    cancelled = []
    window.job.cancelled.connect(lambda: cancelled.append(True))
    window.open_replay(fixture_dem)
    assert window.stack.currentWidget() is window.loading
    window.loading.cancel.click()  # the loading view's own Cancel button
    assert cancelled and not window.job.running
    assert window.stack.currentWidget() is window.empty
    assert window.open_action.isEnabled() and window.topbar.open_button.isEnabled()
    assert window.topbar.status.text() == "Cancelled"


def test_a_wrong_file_is_refused_without_starting_a_parse(window, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(args[2]))
    junk = tmp_path / "junk.dem"
    junk.write_bytes(b"not a replay")
    window.open_replay(junk)
    assert not window.job.running
    assert window.stack.currentWidget() is window.empty
    assert shown and "not look like" in shown[0]


def test_an_unreadable_replay_reports_a_data_error(window, tmp_path, monkeypatch):
    """A file with a valid header but garbage after it passes the pre-check and fails in the engine."""
    from gemstudio.precheck import MAGIC

    bad = tmp_path / "bad.dem"
    bad.write_bytes(MAGIC + b"\x00" * 64)
    failed = []
    window.job.failed.connect(failed.append)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    window.open_replay(bad)
    assert wait_until(lambda: failed, 60)
    assert failed[0]["kind"] == "replay"
    assert not window.job.running
    assert window.stack.currentWidget() is window.empty


def test_picking_a_fight_in_the_table_opens_it_in_the_figure(window):
    """Native table -> figure: the dashboard's signal calls gemFigure.selectFight in the page."""
    window.show_figure()
    pressed = "document.querySelector('.fights-fig-list [aria-pressed=true]')?.dataset.fight"
    assert wait_until(lambda: (js(window, pressed) or "") != "")
    target = 3 if js(window, pressed) != "3" else 4
    window.dashboard.fight_picked.emit(target)
    assert wait_until(lambda: js(window, pressed) == str(target))


# -- the bridge: figure <-> native table and roster, through the real web view ---------------


def demo_rows(count=36):
    """Fights-table rows numbered like the demo data's fights (1..36)."""
    return [
        {"n": n, "start": f"{n:02d}:00", "score": "1–0", "more": "r", "deaths": 1,
         "gold_r": 0, "gold_d": 0, "next": ""}
        for n in range(1, count + 1)
    ]  # fmt: skip


def demo_players():
    """Roster for the demo fight's heroes (the committed demo replay)."""
    heroes = ["Tiny", "Sniper", "Lion", "Rubick", "Pangolier"]
    return [
        {"player_id": i, "name": f"p{i}", "hero": hero, "icon": hero.lower(), "team": "radiant",
         "kills": 1, "deaths": 1, "assists": 1, "net_worth": 10000}
        for i, hero in enumerate(heroes)
    ]  # fmt: skip


def pressed_fight(window):
    return js(
        window, "document.querySelector('.fights-fig-list [aria-pressed=true]')?.dataset.fight"
    )


def test_the_page_connects_to_the_bridge(window):
    window.show_figure()
    assert wait_until(lambda: window.bridge.is_ready, 20), "the page never called gem.ready()"


def test_a_fight_picked_in_the_figure_selects_its_table_row_without_echo(window):
    window.dashboard.drawer.fights_model.set_rows(demo_rows())
    echoed = []
    window.dashboard.fight_picked.connect(echoed.append)
    window.show_figure()
    assert wait_until(lambda: window.bridge.is_ready, 20)
    assert wait_until(lambda: (pressed_fight(window) or "") != "")

    target = 7 if pressed_fight(window) != "7" else 8
    js(window, f"document.querySelector('.fights-fig-list [data-fight=\"{target}\"]').click()")
    table = window.dashboard.drawer.fights_view
    assert wait_until(lambda: table.currentIndex().isValid())
    selected = table.model().data(table.currentIndex(), ROW_ROLE)
    assert selected["n"] == target
    QTest.qWait(300)
    assert echoed == []  # following the figure must not send the pick back to it


def test_a_row_picked_in_the_table_opens_that_fight_in_the_figure(window):
    window.dashboard.drawer.fights_model.set_rows(demo_rows())
    window.show_figure()
    assert wait_until(lambda: window.bridge.is_ready, 20)
    assert wait_until(lambda: (pressed_fight(window) or "") != "")
    target = 9 if pressed_fight(window) != "9" else 10
    window.dashboard.drawer.fights_view.selectRow(target - 1)  # rows are numbered from 1
    assert wait_until(lambda: pressed_fight(window) == str(target))


def test_a_pick_made_before_the_page_loaded_is_applied_when_it_connects(window):
    window.dashboard.drawer.fights_model.set_rows(demo_rows())
    window.dashboard.drawer.fights_view.selectRow(4)  # fight 5; the page is not loaded yet
    window.show_figure()
    assert wait_until(lambda: pressed_fight(window) == "5", 25)


def follow_buttons(window):
    return "document.querySelectorAll('[data-status] .fight-status-hero').length"


def test_following_a_hero_in_the_figure_marks_the_roster_player(window):
    window.dashboard.rail.load(demo_players(), {"radiant": 50000, "dire": 0})
    window.show_figure()
    assert wait_until(lambda: window.bridge.is_ready, 20)
    assert wait_until(lambda: (js(window, follow_buttons(window)) or 0) > 0, 30)
    js(
        window,
        "document.querySelector('[data-status] .fight-status-hero[title=\"Follow Tiny\"]').click()",
    )
    buttons = {b.property("hero"): b for b in window.dashboard.rail._buttons}
    assert wait_until(lambda: buttons["Tiny"].isChecked())
    assert not buttons["Sniper"].isChecked()


def test_a_roster_player_clicked_follows_that_hero_in_the_figure(window):
    window.dashboard.rail.load(demo_players(), {"radiant": 50000, "dire": 0})
    window.show_figure()
    assert wait_until(lambda: window.bridge.is_ready, 20)
    assert wait_until(lambda: (js(window, follow_buttons(window)) or 0) > 0, 30)
    sniper = next(b for b in window.dashboard.rail._buttons if b.property("hero") == "Sniper")
    sniper.click()
    pressed = "document.querySelector('[data-status] .fight-status-hero[aria-pressed=true]')?.title"
    assert wait_until(lambda: js(window, pressed) == "Follow Sniper")


# -- the native playback controls, driving the real fight player ------------------------------


def transport_ready(window):
    return window.dashboard.transport.state is not None


def page_scrub(window):
    return js(window, "Number(document.querySelector('[data-scrub]')?.value)")


def page_playing(window):
    return js(window, "Boolean(document.querySelector('.is-playing'))")


def open_demo_player(window):
    window.show_figure()
    assert wait_until(lambda: window.bridge.is_ready, 20)
    assert wait_until(lambda: transport_ready(window), 30), "the player never reported its state"
    return window.dashboard.transport


def test_the_controls_start_disabled_and_enable_when_a_fight_has_a_player(window):
    assert window.dashboard.transport.state is None
    transport = open_demo_player(window)
    assert transport.play.isEnabled() and transport.state.duration > 20


def test_play_and_pause_from_the_native_button(window):
    transport = open_demo_player(window)
    # The player starts paused only if the page has not scrolled it into view; settle first.
    if page_playing(window):
        transport.play.click()
        assert wait_until(lambda: not page_playing(window))
    transport.play.click()
    assert wait_until(lambda: page_playing(window))
    assert wait_until(lambda: transport.play.text() == PAUSE)
    transport.play.click()
    assert wait_until(lambda: not page_playing(window))
    assert wait_until(lambda: transport.play.text() == PLAY)


def test_pressing_play_in_the_page_updates_the_native_button(window):
    transport = open_demo_player(window)
    if page_playing(window):
        js(window, "document.querySelector('[data-play]').click()")
        assert wait_until(lambda: transport.play.text() == PLAY)
    js(window, "document.querySelector('[data-play]').click()")
    assert wait_until(lambda: transport.play.text() == PAUSE)


def test_seeking_with_the_slider_and_the_step_buttons(window):
    transport = open_demo_player(window)
    if page_playing(window):
        transport.play.click()
        assert wait_until(lambda: not page_playing(window))
    transport.slider.setValue(50)  # 5.0 s
    assert wait_until(lambda: abs(page_scrub(window) - 5.0) < 0.2)
    assert wait_until(lambda: abs(transport.state.seconds - 5.0) < 0.2)
    transport.forward.click()
    assert wait_until(lambda: abs(page_scrub(window) - 15.0) < 0.2)
    transport.back.click()
    transport.back.click()  # 15 -> 5 -> clamped at 0
    assert wait_until(lambda: page_scrub(window) < 0.2)


def test_speed_chips_change_the_players_speed(window):
    transport = open_demo_player(window)
    transport.chips[4.0].click()
    pressed = "document.querySelector('[data-speeds] [aria-pressed=true]')?.textContent"
    assert wait_until(lambda: js(window, pressed) == "4×")
    assert wait_until(lambda: transport.chips[4.0].isChecked())
    transport.chips[0.5].click()
    assert wait_until(lambda: js(window, pressed) == "0.5×")


def test_space_toggles_playback_through_the_window_shortcut(window):
    transport = open_demo_player(window)
    if page_playing(window):
        transport.toggle_action.trigger()
        assert wait_until(lambda: not page_playing(window))
    assert transport.toggle_action in window.actions()
    transport.toggle_action.trigger()
    assert wait_until(lambda: page_playing(window))


def test_a_breakdown_only_fight_keeps_working_controls_with_its_own_length(window):
    """Fights with fewer than 3 deaths have no map, but their feed and timeline still play."""
    transport = open_demo_player(window)
    first = transport.state.duration
    window.bridge.request_fight(1)  # the demo's first fight: 1 death, a breakdown without a map
    assert wait_until(lambda: transport.state is not None and transport.state.duration != first, 20)
    assert transport.play.isEnabled()
    transport.slider.setValue(100)  # 10.0 s into that fight
    assert wait_until(lambda: abs(page_scrub(window) - 10.0) < 0.2)


# -- one tab per figure ----------------------------------------------------------------------

FIGURE_TABS = [
    (1, "objectives", "Objectives"),
    (2, "lanes", "Lanes"),
    (3, "runes", "Runes"),
    (4, "lead", "Gold && XP Lead"),
    (5, "wards", "Wards"),
]


def page_js(page, script, timeout_s=10.0):
    box = []
    page.page.runJavaScript(script, box.append)
    assert wait_until(lambda: box, timeout_s), f"no result for {script}"
    return box[0]


def mounted(page, name):
    """A figure is mounted when its controls (hidden until then) are shown."""
    return page_js(
        page,
        f"document.querySelector('[data-recipe-figure=\"{name}\"] [data-controls]')?.hidden === false",
    )


def test_every_figure_has_its_own_tab_and_unbuilt_sections_are_disabled(window):
    bar = window.sections
    assert [bar.tabText(i) for i in range(6)] == [
        "Fight Replay && Dashboard",
        "Objectives",
        "Lanes",
        "Runes",
        "Gold && XP Lead",
        "Wards",
    ]
    assert all(bar.isTabEnabled(i) for i in range(6))
    assert [bar.tabText(i) for i in (6, 7)] == ["Scoreboard && Players", "Batch && Parquet Export"]
    assert not bar.isTabEnabled(6) and not bar.isTabEnabled(7)


@pytest.mark.parametrize(("index", "name", "_title"), FIGURE_TABS)
def test_a_figure_renders_on_its_tab_without_errors(window, index, name, _title):
    window.show_figure()
    window.sections.setCurrentIndex(index)
    page = window.pages[name]
    assert window.dashboard.pages.currentWidget() is page.view
    assert wait_until(lambda: mounted(page, name) is True, 30), f"{name} never mounted"
    assert page.errors == [], page.errors
    assert not window.dashboard.transport.isVisible()  # playback controls are for Fights only
    window.sections.setCurrentIndex(0)
    assert window.dashboard.pages.currentWidget() is window.view
    assert window.dashboard.transport.isVisible()


def test_figure_pages_are_created_only_when_their_tab_is_shown(window):
    window.show_figure()
    assert set(window.pages) == {"fights"}
    window.sections.setCurrentIndex(3)
    assert set(window.pages) == {"fights", "runes"}
    window.sections.setCurrentIndex(3)  # revisiting loads nothing twice
    assert window.pages["runes"].token == window._token


def test_a_page_reloads_for_a_new_replay_when_it_is_shown_again(window):
    window.show_figure()
    window.sections.setCurrentIndex(5)
    wards = window.pages["wards"]
    assert wait_until(lambda: mounted(wards, "wards") is True, 30)
    window.sections.setCurrentIndex(0)
    window._token += 1  # what opening another replay does
    assert wards.token != window._token
    window.sections.setCurrentIndex(5)
    assert wards.token == window._token  # reloaded for the new replay


def test_a_fight_link_in_a_figure_opens_that_fight_in_the_fights_tab(window):
    window.show_figure()
    window.sections.setCurrentIndex(1)
    page = window.pages["objectives"]
    assert wait_until(lambda: mounted(page, "objectives") is True, 30)
    # A fight link appears in the detail of a picked objective ("Open fight N"), so pick one.
    # The figure re-renders just after it mounts, so keep picking until the link is there.
    # (runJavaScript does not return a raw JavaScript array reliably, so send JSON text.)
    links = (
        "JSON.stringify([...document.querySelectorAll('a[href*=\"#fight-\"]')]"
        ".map(a => a.getAttribute('href')))"
    )

    def link_appears():
        # Clicking a picked objective un-picks it, so only click one that is not picked.
        page_js(
            page,
            "(() => { const b = document.querySelector('li button');"
            " if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); })()",
        )
        QTest.qWait(400)
        return len(json.loads(page_js(page, links) or "[]")) > 0

    assert wait_until(link_appears, 20), "no fight link rendered"
    href = json.loads(page_js(page, links))[0]
    number = href.rsplit("#fight-", 1)[1]
    page_js(page, "document.querySelector('a[href*=\"#fight-\"]').click()")
    assert wait_until(lambda: window.sections.currentIndex() == 0, 10)
    assert window.dashboard.pages.currentWidget() is window.view
    assert wait_until(lambda: pressed_fight(window) == number, 30)
    assert page.view.url().path().endswith("objectives.html")  # the figure page did not navigate


def test_figures_handle_a_replay_with_no_events(window, fixture_dem):
    """The truncated fixture has no fights, objectives, wards or runes: nothing may throw."""
    finished = []
    window.job.finished.connect(finished.append)
    window.open_replay(fixture_dem)
    assert wait_until(lambda: finished, 120)
    for index, name, _title in FIGURE_TABS:
        window.sections.setCurrentIndex(index)
        page = window.pages[name]
        if name == "lead":
            # The site's lead figure cannot draw an empty curve; the page says so instead.
            text = "document.body.textContent"
            assert wait_until(
                lambda page=page, t=text: "No minute-by-minute" in (page_js(page, t) or ""), 30
            )
        else:
            assert wait_until(lambda page=page, name=name: mounted(page, name) is True, 30), name
        assert page.errors == [], (name, page.errors)


# -- the Fights tab layout: replay and log on top (60/40), all-fights map behind a button ------

LAYOUT_JS = """JSON.stringify((() => {
  const r = s => { const e = document.querySelector(s); if (!e) return null;
    const b = e.getBoundingClientRect();
    return {x: b.x, y: b.y, w: b.width, h: b.height, shown: getComputedStyle(e).display !== 'none'}; };
  const t = document.querySelector('.all-fights-toggle');
  return {map: r('.fights-panel-map'), log: r('.fights-panel-feed'), feed: r('.feed'),
          list: r('.fights-fig-list'), all: r('.fights-fig-body'),
          button: t?.textContent, pressed: t?.getAttribute('aria-pressed')};
})())"""


def layout(window):
    return json.loads(js(window, LAYOUT_JS))


def layout_ready(window):
    found = layout(window)
    return bool(found["map"] and found["log"] and found["map"]["w"] > 0 and found["feed"])


def test_the_replay_and_the_fight_log_sit_on_top_split_sixty_forty(window):
    window.resize(1440, 1000)
    window.show_figure()
    assert wait_until(lambda: layout_ready(window), 30), "the replay panel never appeared"
    found = layout(window)
    replay, log = found["map"], found["log"]
    share = replay["w"] / (replay["w"] + log["w"])
    assert abs(share - 0.60) < 0.02, f"replay is {share:.1%} of the row, not 60%"
    assert abs(replay["h"] - log["h"]) <= 2  # the log is as tall as the replay and scrolls inside
    assert abs(replay["y"] - log["y"]) <= 1  # side by side
    assert replay["y"] < found["list"]["y"]  # the replay is above the fight list


def test_the_all_fights_map_is_hidden_until_its_button_is_pressed(window):
    window.show_figure()
    assert wait_until(lambda: layout(window).get("button") is not None, 30)
    found = layout(window)
    assert found["all"]["shown"] is False
    assert found["button"] == "All fights map" and found["pressed"] == "false"
    toggle = "document.querySelector('.all-fights-toggle').click(); 1"
    js(window, toggle)
    assert wait_until(lambda: layout(window)["all"]["shown"] is True)
    opened = layout(window)
    assert opened["button"] == "Hide the all-fights map" and opened["pressed"] == "true"
    # With the map open the fights are on it, and still below the replay.
    dots = "document.querySelectorAll('[data-fights] [data-fight]').length"
    assert js(window, dots) > 0 and opened["all"]["y"] > opened["map"]["y"]
    js(window, toggle)
    assert wait_until(lambda: layout(window)["all"]["shown"] is False)
    assert layout(window)["button"] == "All fights map"


def test_picking_a_fight_on_the_all_fights_map_still_opens_its_replay(window):
    window.show_figure()
    assert wait_until(lambda: layout_ready(window), 30)
    js(window, "document.querySelector('.all-fights-toggle').click(); 1")
    assert wait_until(lambda: layout(window)["all"]["shown"] is True)
    shown = pressed_fight(window)
    target = "3" if shown != "3" else "4"
    js(
        window,
        f"document.querySelector('[data-fights] [data-fight=\"{target}\"]').dispatchEvent(new MouseEvent('click', {{bubbles: true}})); 1",
    )
    assert wait_until(lambda: pressed_fight(window) == target, 20)


# -- stepping through fights: arrows, and a timeline that clicks instead of filtering ------------

NAV_JS = """JSON.stringify((() => {
  const items = [...document.querySelectorAll('.fights-fig-list [data-fight]')];
  const open = items.findIndex(b => b.getAttribute('aria-pressed') === 'true');
  const btn = label => [...document.querySelectorAll('.fight-nav button')].find(b => b.getAttribute('aria-label') === label);
  const pill = document.querySelector('.range-pill');
  return {listed: items.map(b => Number(b.dataset.fight)), open: open < 0 ? null : Number(items[open].dataset.fight),
          label: document.querySelector('.fight-nav-label')?.textContent ?? null,
          kind: document.querySelector('.fight-nav-kind')?.textContent ?? null,
          previousDisabled: btn('Previous fight')?.disabled, nextDisabled: btn('Next fight')?.disabled,
          panel: !!document.querySelector('.fights-panel'), pillShown: !!pill && getComputedStyle(pill).display !== 'none'};
})())"""


def nav(window):
    return json.loads(js(window, NAV_JS))


def open_fight_and_wait(window, number):
    js(window, f"document.querySelector('.fights-fig-list [data-fight=\"{number}\"]').click(); 1")
    assert wait_until(lambda: nav(window)["open"] == number, 20)


def press_nav(window, label):
    js(
        window,
        f"[...document.querySelectorAll('.fight-nav button')].find(b => b.getAttribute('aria-label') === '{label}').click(); 1",
    )


def pointer_on_timeline(window, steps):
    """Fire pointer events on the timeline: steps is a list of (type, fraction of its width)."""
    script = (
        "(() => { const svg = document.querySelector('[data-timeline] svg'); const r = svg.getBoundingClientRect();"
        " const fire = (type, f) => svg.dispatchEvent(new PointerEvent(type, {clientX: r.left + r.width * f,"
        " clientY: r.top + r.height / 2, bubbles: true, pointerId: 1, isPrimary: true}));"
        f" for (const [type, f] of {json.dumps(steps)}) fire(type, f); return 1; }})()"
    )
    js(window, script)


def test_the_arrows_step_through_the_fights_and_stop_at_the_ends(window):
    window.show_figure()
    assert wait_until(
        lambda: nav(window)["label"] is not None and nav(window)["open"] is not None, 30
    )
    listed = nav(window)["listed"]
    assert len(listed) > 5
    open_fight_and_wait(window, listed[0])
    state = nav(window)
    assert (
        state["previousDisabled"] is True and state["nextDisabled"] is False
    )  # at the first fight
    assert f"Fight {listed[0]}" in state["label"] and f"(1 of {len(listed)})" in state["label"]
    press_nav(window, "Next fight")
    assert wait_until(lambda: nav(window)["open"] == listed[1], 20)
    assert f"(2 of {len(listed)})" in nav(window)["label"]
    press_nav(window, "Previous fight")
    assert wait_until(lambda: nav(window)["open"] == listed[0], 20)
    open_fight_and_wait(window, listed[-1])
    assert nav(window)["nextDisabled"] is True and nav(window)["previousDisabled"] is False


def test_the_label_says_whether_the_open_fight_has_a_map_replay(window):
    window.show_figure()
    assert wait_until(lambda: nav(window)["open"] is not None and nav(window)["kind"], 30)
    # The demo data's fight 1 has one death: a breakdown, no map.
    open_fight_and_wait(window, 1)
    assert "Breakdown only" in nav(window)["kind"]
    # Its biggest fight has a map replay.
    listed = nav(window)["listed"]
    with_map = [
        n for n in listed
        if json.loads(js(window, f"JSON.stringify(document.querySelector('.fights-fig-list [data-fight=\"{n}\"]').textContent.includes('playback'))"))
    ]  # fmt: skip
    assert with_map
    open_fight_and_wait(window, with_map[0])
    assert nav(window)["kind"] == "Map replay"


def test_dragging_on_the_timeline_no_longer_changes_or_closes_the_replay(window):
    """The site treats a drag as a filter and swaps or closes the open fight; here it does nothing."""
    window.show_figure()
    assert wait_until(lambda: nav(window)["open"] is not None and nav(window)["panel"], 30)
    before = nav(window)
    pointer_on_timeline(
        window,
        [("pointerdown", 0.20), ("pointermove", 0.40), ("pointermove", 0.60), ("pointerup", 0.60)],
    )
    QTest.qWait(700)
    after = nav(window)
    assert after["open"] == before["open"]  # the same fight is still open
    assert after["panel"] is True  # the replay did not close
    assert after["listed"] == before["listed"]  # no stretch filter was applied
    assert after["pillShown"] is False
    # A drag that would have picked a stretch with no fight in it (the very start) is harmless too.
    pointer_on_timeline(window, [("pointerdown", 0.0), ("pointermove", 0.01), ("pointerup", 0.012)])
    QTest.qWait(500)
    assert nav(window)["open"] == before["open"] and nav(window)["panel"] is True


def test_clicking_a_fight_on_the_timeline_opens_it(window):
    window.show_figure()
    assert wait_until(lambda: nav(window)["open"] is not None, 30)
    listed = nav(window)["listed"]
    target_index = 10 if listed[10] != nav(window)["open"] else 11
    fraction = js(
        window,
        "(() => { const svg = document.querySelector('[data-timeline] svg'); const r = svg.getBoundingClientRect();"
        f" const b = document.querySelectorAll('.fight-bar')[{target_index}].getBoundingClientRect();"
        " return (b.left + b.width / 2 - r.left) / r.width; })()",
    )
    pointer_on_timeline(window, [("pointerdown", fraction), ("pointerup", fraction)])
    assert wait_until(lambda: nav(window)["open"] == listed[target_index], 20)
    assert nav(window)["panel"] is True


def test_the_arrows_follow_the_size_filter(window):
    window.show_figure()
    assert wait_until(lambda: nav(window)["open"] is not None, 30)
    everything = len(nav(window)["listed"])
    js(
        window,
        "[...document.querySelectorAll('.fights-fig-controls .chip')].find(b => b.textContent.trim() === '3+').click(); 1",
    )
    assert wait_until(lambda: len(nav(window)["listed"]) < everything, 20)
    filtered = nav(window)
    assert filtered["open"] in filtered["listed"]
    assert f"of {len(filtered['listed'])})" in filtered["label"]
    # Stepping stays inside the filtered fights.
    first = filtered["listed"][0]
    open_fight_and_wait(window, first)
    press_nav(window, "Next fight")
    assert wait_until(lambda: nav(window)["open"] == filtered["listed"][1], 20)
