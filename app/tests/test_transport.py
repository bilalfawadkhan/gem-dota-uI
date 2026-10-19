from gemstudio.transport import DISABLED_TIP, PAUSE, PLAY, Playback, TransportBar


def make(qapp, **kw):
    bar = TransportBar()
    events = []
    bar.play_requested.connect(lambda v: events.append(("play", v)))
    bar.seek_requested.connect(lambda s: events.append(("seek", round(s, 3))))
    bar.speed_requested.connect(lambda x: events.append(("speed", x)))
    state = {"playing": False, "clock": "14:30", "seconds": 25.0, "duration": 51.0, "speed": 2.0}
    state.update(kw)
    return bar, events, Playback(**state)


def test_everything_is_disabled_until_a_fight_has_a_player(qapp):
    bar, _, _ = make(qapp)
    controls = (bar.back, bar.play, bar.forward, bar.slider, *bar.chips.values())
    assert all(not widget.isEnabled() for widget in controls)
    assert all(not action.isEnabled() for action in bar.actions_with_shortcuts)
    assert bar.play.toolTip() == DISABLED_TIP and bar.time.text() == ""
    assert bar.slider.maximum() == 0 and bar.state is None


def test_it_mirrors_what_the_player_reports(qapp):
    bar, events, state = make(qapp)
    bar.set_state(state)
    assert all(w.isEnabled() for w in (bar.back, bar.play, bar.forward, bar.slider))
    assert bar.play.text() == PLAY and "14:30" in bar.time.text()
    assert "25.0 / 51 s" in bar.time.text()
    assert (bar.slider.maximum(), bar.slider.value()) == (510, 250)
    assert [s for s, chip in bar.chips.items() if chip.isChecked()] == [2.0]
    bar.set_state(Playback(True, "14:31", 26.0, 51.0, 0.5))
    assert bar.play.text() == PAUSE
    assert [s for s, chip in bar.chips.items() if chip.isChecked()] == [0.5]
    assert events == []  # mirroring the page never sends commands back


def test_play_button_asks_for_the_opposite_of_the_state(qapp):
    bar, events, state = make(qapp)
    bar.set_state(state)
    bar.play.click()
    bar.set_state(Playback(True, "14:30", 25.0, 51.0, 2.0))
    bar.play.click()
    assert events == [("play", True), ("play", False)]


def test_step_moves_ten_seconds_within_the_fight(qapp):
    bar, events, state = make(qapp)
    bar.set_state(state)
    bar.forward.click()
    bar.back.click()
    assert events == [("seek", 35.0), ("seek", 15.0)]
    events.clear()
    bar.set_state(Playback(False, "x", 4.0, 51.0, 2.0))
    bar.back.click()  # clamps at the start
    bar.set_state(Playback(False, "x", 48.0, 51.0, 2.0))
    bar.forward.click()  # and at the end
    assert events == [("seek", 0.0), ("seek", 51.0)]


def test_a_step_while_playing_resumes_playing_after_the_seek(qapp):
    """The figure's player pauses on a seek, so the bar asks it to play again."""
    bar, events, _ = make(qapp)
    bar.set_state(Playback(True, "14:30", 25.0, 51.0, 2.0))
    bar.forward.click()
    assert events == [("seek", 35.0), ("play", True)]  # in this order


def test_dragging_the_slider_seeks_in_seconds_but_following_the_page_does_not(qapp):
    bar, events, state = make(qapp)
    bar.set_state(state)
    bar.slider.setValue(123)  # as a user drag does
    assert events == [("seek", 12.3)]
    events.clear()
    bar.set_state(Playback(False, "14:31", 40.0, 51.0, 2.0))
    assert bar.slider.value() == 400 and events == []


def test_the_slider_is_left_alone_while_the_user_holds_it(qapp):
    bar, _, state = make(qapp)
    bar.set_state(state)
    bar.slider.setSliderDown(True)
    bar.set_state(Playback(False, "14:31", 40.0, 51.0, 2.0))
    assert bar.slider.value() == 250  # the page's report did not pull it away from the hand
    bar.slider.setSliderDown(False)


def test_speed_chips_send_their_speed(qapp):
    bar, events, state = make(qapp)
    bar.set_state(state)
    bar.chips[4.0].click()
    bar.chips[0.25].click()
    assert events == [("speed", 4.0), ("speed", 0.25)]


def test_shortcut_actions_do_the_same_as_the_buttons(qapp):
    bar, events, state = make(qapp)
    bar.set_state(state)
    bar.toggle_action.trigger()
    bar.forward_action.trigger()
    assert events == [("play", True), ("seek", 35.0)]
    assert bar.toggle_action.shortcut().toString() == "Space"
