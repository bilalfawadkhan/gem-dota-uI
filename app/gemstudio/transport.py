"""Native playback controls for the figure's fight player.

A bar above the figure with Play/Pause, -10 s / +10 s steps, a seek slider, the clock, and
speed chips. It mirrors the player (the page reports its state through the bridge) and sends
the user's commands back; it holds no playback state of its own beyond the last report.

Shortcuts (window-wide): Space plays or pauses, Ctrl+Left / Ctrl+Right step 10 s.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0)
STEP_SECONDS = 10.0
#: The slider counts tenths of a second.
TICKS_PER_SECOND = 10
PLAY, PAUSE = "▶", "❚❚"
DISABLED_TIP = "Open a fight to use the playback controls"


@dataclass(frozen=True)
class Playback:
    """The player's state, as the page reports it.

    Attributes:
        playing: Whether it is playing.
        clock: The match clock text the player shows, e.g. ``"14:30"``.
        seconds: Seconds into the open fight.
        duration: The fight's length in seconds.
        speed: Playback speed multiplier.
    """

    playing: bool
    clock: str
    seconds: float
    duration: float
    speed: float


class TransportBar(QWidget):
    """Play/pause, step, seek, clock and speed for the open fight.

    Signals:
        play_requested(bool): True to play, False to pause.
        seek_requested(float): Seconds into the fight.
        speed_requested(float): A speed multiplier.
    """

    play_requested = Signal(bool)
    seek_requested = Signal(float)
    speed_requested = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("transport")
        self._state: Playback | None = None
        self._programmatic = False  # True while the slider is moved to follow the page

        self.back = QPushButton("−10 s")
        self.play = QPushButton(PLAY)
        self.forward = QPushButton("+10 s")
        for button in (self.back, self.forward):
            button.setObjectName("transportButton")
        self.play.setObjectName("transportPlay")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimumWidth(160)
        self.time = QLabel("")
        self.time.setObjectName("time")
        self.time.setMinimumWidth(150)

        self.chips: dict[float, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for speed in SPEEDS:
            chip = QPushButton(f"{speed:g}×")
            chip.setObjectName("speedChip")
            chip.setCheckable(True)
            group.addButton(chip)
            chip.clicked.connect(lambda _=False, s=speed: self.speed_requested.emit(s))
            self.chips[speed] = chip

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)
        for widget in (self.back, self.play, self.forward):
            layout.addWidget(widget)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.time)
        for chip in self.chips.values():
            layout.addWidget(chip)

        self.toggle_action = self._action("Play / pause", "Space", self.toggle)
        self.back_action = self._action("Back 10 s", "Ctrl+Left", lambda: self.step(-STEP_SECONDS))
        self.forward_action = self._action(
            "Forward 10 s", "Ctrl+Right", lambda: self.step(STEP_SECONDS)
        )
        self.play.clicked.connect(self.toggle)
        self.back.clicked.connect(lambda: self.step(-STEP_SECONDS))
        self.forward.clicked.connect(lambda: self.step(STEP_SECONDS))
        self.slider.valueChanged.connect(self._slider_moved)
        self.set_state(None)

    def _action(self, text: str, shortcut: str, slot: object) -> QAction:
        action = QAction(text, self)
        action.setShortcut(shortcut)
        action.triggered.connect(slot)  # type: ignore[arg-type]
        return action

    @property
    def actions_with_shortcuts(self) -> list[QAction]:
        """The shortcut actions, for the window to register."""
        return [self.toggle_action, self.back_action, self.forward_action]

    @property
    def state(self) -> Playback | None:
        """The last reported playback, or None when no fight has a player."""
        return self._state

    def set_state(self, state: Playback | None) -> None:
        """Show the player's state, or disable the controls when there is none.

        Args:
            state: What the page last reported, or None when no fight has a player.
        """
        self._state = state
        enabled = state is not None
        for widget in (self.back, self.play, self.forward, self.slider, *self.chips.values()):
            widget.setEnabled(enabled)
            widget.setToolTip("" if enabled else DISABLED_TIP)
        for action in self.actions_with_shortcuts:
            action.setEnabled(enabled)
        if state is None:
            self.play.setText(PLAY)
            self.time.setText("")
            self._set_slider(0, 0)
            for chip in self.chips.values():
                chip.setChecked(False)
            return
        self.play.setText(PAUSE if state.playing else PLAY)
        self.play.setToolTip("Pause (Space)" if state.playing else "Play (Space)")
        self.back.setToolTip("Back 10 s (Ctrl+Left)")
        self.forward.setToolTip("Forward 10 s (Ctrl+Right)")
        self.time.setText(f"{state.clock}  {state.seconds:4.1f} / {state.duration:.0f} s")
        if not self.slider.isSliderDown():  # do not fight the user's drag
            self._set_slider(state.seconds, state.duration)
        for speed, chip in self.chips.items():
            chip.setChecked(abs(speed - state.speed) < 1e-6)

    def toggle(self) -> None:
        """Ask to play, or to pause when it is playing."""
        if self._state is not None:
            self.play_requested.emit(not self._state.playing)

    def step(self, delta: float) -> None:
        """Move the playback by ``delta`` seconds, staying within the fight.

        A seek pauses the figure's player, so a step taken while playing asks it to play
        again afterwards.

        Args:
            delta: Seconds to move (negative goes back).
        """
        state = self._state
        if state is None:
            return
        self.seek_requested.emit(min(max(state.seconds + delta, 0.0), state.duration))
        if state.playing:
            self.play_requested.emit(True)

    def _set_slider(self, seconds: float, duration: float) -> None:
        self._programmatic = True
        try:
            self.slider.setRange(0, round(duration * TICKS_PER_SECOND))
            self.slider.setValue(round(seconds * TICKS_PER_SECOND))
        finally:
            self._programmatic = False

    def _slider_moved(self, value: int) -> None:
        if not self._programmatic and self._state is not None:
            self.seek_requested.emit(value / TICKS_PER_SECOND)
