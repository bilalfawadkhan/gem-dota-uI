"""The loading view shown while a replay is read.

A full replay is slow to read (about 3.5 minutes for a 36-minute match the first time), and
the engine reports no finer progress than which steps are running. So this view says exactly
that and no more: it names each step and its state, shows the time elapsed, and explains that
the result is saved. It does not show a percentage or an estimated time left, because there is
no measurement to base one on.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

#: (task name, label), in the order the job runs them.
STEPS = (
    ("parse", "Reading the replay: players, combat log, fights, wards"),
    ("states", "Tracking every hero's position, health and mana"),
    ("places", "Locating buildings and Roshan"),
    ("export", "Preparing the figures"),
)
MARKS = {"waiting": "○", "running": "●", "done": "✓"}


def format_elapsed(seconds: float) -> str:
    """``83.4`` -> ``"1:23"``."""
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class LoadingView(QWidget):
    """Progress view: step list, busy bar, elapsed time, and Cancel.

    Signals:
        cancel_requested(): The user pressed Cancel.
    """

    cancel_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.setObjectName("canvas")
        self._started = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(560)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        self.title = QLabel("Reading replay")
        self.title.setObjectName("loadTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)  # busy: there is no measured progress to show
        self.bar.setTextVisible(False)

        steps = QGridLayout()
        steps.setHorizontalSpacing(10)
        steps.setVerticalSpacing(8)
        self._marks: dict[str, QLabel] = {}
        self._labels: dict[str, QLabel] = {}
        for row, (name, text) in enumerate(STEPS):
            mark, label = QLabel(MARKS["waiting"]), QLabel(text)
            mark.setObjectName("stepMark")
            label.setObjectName("step")
            self._marks[name], self._labels[name] = mark, label
            steps.addWidget(mark, row, 0)
            steps.addWidget(label, row, 1)
            steps.setColumnStretch(1, 1)

        self.elapsed = QLabel("Elapsed 0:00")
        self.elapsed.setObjectName("mono")
        self.note = QLabel(
            "The first time a replay is opened this takes a few minutes: about 3½ minutes for a "
            "36-minute match. The result is saved, so opening it again is quick."
        )
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self.cancel_requested)

        footer = QHBoxLayout()
        footer.addWidget(self.elapsed)
        footer.addStretch()
        footer.addWidget(self.cancel)

        for widget in (self.title, self.subtitle, self.bar):
            layout.addWidget(widget)
        layout.addLayout(steps)
        layout.addWidget(self.note)
        layout.addLayout(footer)

        outer = QVBoxLayout(self)
        outer.addStretch()
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()
        self.set_states({})

    def begin(self, name: str, size_mb: float) -> None:
        """Start showing a replay's progress.

        Args:
            name: The replay's file name.
            size_mb: Its size, shown as context.
        """
        self.title.setText("Reading replay")
        self.subtitle.setText(f"{name} · {size_mb:.0f} MB")
        self.set_states({})
        self._started = time.monotonic()
        self.elapsed.setText("Elapsed 0:00")
        self._timer.start()

    def end(self) -> None:
        """Stop the elapsed-time clock."""
        self._timer.stop()

    def set_states(self, states: dict[str, str]) -> None:
        """Show each step as waiting, running or done.

        Args:
            states: Step name to ``"waiting"``, ``"running"`` or ``"done"``; missing means waiting.
        """
        for name, _ in STEPS:
            state = states.get(name, "waiting")
            self._marks[name].setText(MARKS[state])
            for widget in (self._marks[name], self._labels[name]):
                widget.setProperty("state", state)
                _repolish(widget)

    def _tick(self) -> None:
        self.elapsed.setText(f"Elapsed {format_elapsed(time.monotonic() - self._started)}")
