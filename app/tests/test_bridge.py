from gemstudio.bridge import Bridge


def record(bridge):
    sent = []
    bridge.selectFightRequested.connect(lambda n: sent.append(("fight", n)))
    bridge.highlightHeroRequested.connect(lambda h: sent.append(("hero", h)))
    return sent


def test_commands_go_straight_to_a_ready_page(qapp):
    bridge, sent = Bridge(), None
    sent = record(bridge)
    bridge.ready()
    bridge.request_fight(5)
    bridge.request_hero("Tiny")
    assert sent == [("fight", 5), ("hero", "Tiny")]


def test_commands_made_before_the_page_connects_are_kept_and_sent_once(qapp):
    bridge = Bridge()
    sent = record(bridge)
    bridge.request_fight(3)
    bridge.request_fight(8)  # the latest of each kind wins
    bridge.request_hero("Lion")
    assert sent == [] and not bridge.is_ready
    bridge.ready()
    assert sent == [("fight", 8), ("hero", "Lion")]
    bridge.ready()  # a second ready does not resend
    assert sent == [("fight", 8), ("hero", "Lion")]


def test_reset_makes_the_next_commands_wait_for_the_new_page(qapp):
    bridge = Bridge()
    sent = record(bridge)
    bridge.ready()
    bridge.reset()
    assert not bridge.is_ready
    bridge.request_fight(2)
    assert sent == []
    bridge.ready()
    assert sent == [("fight", 2)]


def test_page_events_are_announced_to_the_app(qapp):
    bridge = Bridge()
    heard = []
    bridge.became_ready.connect(lambda: heard.append("ready"))
    bridge.fight_selected.connect(lambda n: heard.append(("fight", n)))
    bridge.hero_followed.connect(lambda h: heard.append(("hero", h)))
    bridge.ready()
    bridge.fightSelected(7)
    bridge.heroFollowed("Sniper")
    assert heard == ["ready", ("fight", 7), ("hero", "Sniper")]


def test_playback_commands_go_to_a_ready_page_and_are_dropped_before_it(qapp):
    bridge = Bridge()
    sent = []
    bridge.seekRequested.connect(lambda s: sent.append(("seek", s)))
    bridge.playRequested.connect(lambda: sent.append("play"))
    bridge.pauseRequested.connect(lambda: sent.append("pause"))
    bridge.speedRequested.connect(lambda x: sent.append(("speed", x)))
    bridge.request_seek(3)
    bridge.request_playing(True)
    assert sent == []  # the controls are disabled until the page reports a player
    bridge.ready()
    bridge.request_seek(12.5)
    bridge.request_playing(True)
    bridge.request_playing(False)
    bridge.request_speed(4)
    assert sent == [("seek", 12.5), "play", "pause", ("speed", 4.0)]


def test_the_players_state_is_announced_to_the_app(qapp):
    bridge = Bridge()
    heard = []
    bridge.playback_changed.connect(lambda *args: heard.append(args))
    bridge.playbackChanged(True, False, "14:30", 12.5, 51.0, 2.0)
    assert heard == [(True, False, "14:30", 12.5, 51.0, 2.0)]
