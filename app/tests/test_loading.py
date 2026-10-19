from gemstudio.loading import MARKS, STEPS, LoadingView, format_elapsed


def test_format_elapsed():
    assert format_elapsed(0) == "0:00" and format_elapsed(83.4) == "1:23"
    assert format_elapsed(213) == "3:33" and format_elapsed(3725) == "62:05"


def test_the_steps_match_what_the_job_runs():
    from gemstudio.jobs import STEP_NAMES

    assert tuple(name for name, _ in STEPS) == STEP_NAMES


def test_begin_shows_the_file_and_resets_the_steps(qapp):
    view = LoadingView()
    view.set_states({"parse": "done"})
    view.begin("match.dem", 67.3)
    assert view.subtitle.text() == "match.dem · 67 MB"
    assert view.elapsed.text() == "Elapsed 0:00"
    assert all(view._marks[name].text() == MARKS["waiting"] for name, _ in STEPS)
    view.end()


def test_each_step_shows_its_state(qapp):
    view = LoadingView()
    view.set_states({"parse": "running", "states": "done"})
    marks = {name: view._marks[name].text() for name, _ in STEPS}
    assert marks == {
        "parse": MARKS["running"],
        "states": MARKS["done"],
        "places": MARKS["waiting"],  # a step not mentioned is waiting
        "export": MARKS["waiting"],
    }
    assert view._labels["parse"].property("state") == "running"


def test_it_promises_no_percentage_or_time_left(qapp):
    """The engine reports no progress; the view must not invent any."""
    view = LoadingView()
    assert view.bar.minimum() == view.bar.maximum() == 0  # busy, not a fraction
    text = view.note.text().lower()
    assert "%" not in text and "remaining" not in text and "left" not in text
    assert "saved" in text  # tells the user the wait happens once
