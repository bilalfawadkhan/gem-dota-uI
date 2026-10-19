"""The Python side of the figure bridge (QWebChannel).

One small object, registered on the page's channel as ``gem``, is all that crosses between
Python and the figure page, and only ids, names and seconds cross it: the figures load their
data by URL. Names are camelCase because the page calls them (see ``app/web/src/bridge.ts``).

    Python -> page   signals ``selectFightRequested(n)``, ``highlightHeroRequested(name)``,
                     ``seekRequested(seconds)``, ``playRequested()``, ``pauseRequested()``,
                     ``speedRequested(x)``
    page -> Python   slots ``ready()``, ``fightSelected(n)``, ``heroFollowed(name)``,
                     ``playbackChanged(...)``, ``openFight(n)``, which the app hears as
                     ``became_ready``, ``fight_selected``, ``hero_followed``,
                     ``playback_changed``, ``fight_requested``

A command sent before the page has connected is kept (the latest of each kind) and sent when
it does, so a click made while a figure is still loading is not lost.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class Bridge(QObject):
    """The ``gem`` object the figure page talks to."""

    # Python -> page (the page connects to these)
    selectFightRequested = Signal(int)
    highlightHeroRequested = Signal(str)
    seekRequested = Signal(float)
    playRequested = Signal()
    pauseRequested = Signal()
    speedRequested = Signal(float)

    # page -> the rest of the app
    became_ready = Signal()
    fight_selected = Signal(int)
    hero_followed = Signal(str)
    #: a link in some figure pointed at a fight: the app should open it in the Fights tab
    fight_requested = Signal(int)
    #: available, playing, clock text, seconds into the fight, fight length in seconds, speed
    playback_changed = Signal(bool, bool, str, float, float, float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ready = False
        self._pending_fight: int | None = None
        self._pending_hero: str | None = None

    @property
    def is_ready(self) -> bool:
        """Whether the current page has connected to the bridge."""
        return self._ready

    def reset(self) -> None:
        """Forget the connection: call before the page is reloaded."""
        self._ready = False

    # -- commands to the page -----------------------------------------------------------

    def request_fight(self, number: int) -> None:
        """Ask the figure to open fight ``number`` (sent when the page is ready)."""
        if self._ready:
            self.selectFightRequested.emit(int(number))
        else:
            self._pending_fight = int(number)

    def request_hero(self, hero: str) -> None:
        """Ask the figure to follow ``hero`` by display name (sent when the page is ready)."""
        if self._ready:
            self.highlightHeroRequested.emit(hero)
        else:
            self._pending_hero = hero

    def request_seek(self, seconds: float) -> None:
        """Move the open fight's playback to ``seconds`` into the fight (needs a ready page)."""
        if self._ready:
            self.seekRequested.emit(float(seconds))

    def request_playing(self, playing: bool) -> None:
        """Play or pause the open fight's playback (needs a ready page)."""
        if self._ready:
            (self.playRequested if playing else self.pauseRequested).emit()

    def request_speed(self, speed: float) -> None:
        """Set the playback speed (needs a ready page)."""
        if self._ready:
            self.speedRequested.emit(float(speed))

    # -- called by the page -------------------------------------------------------------

    @Slot()
    def ready(self) -> None:
        """The page has connected; send what was asked while it loaded."""
        self._ready = True
        self.became_ready.emit()
        fight, hero = self._pending_fight, self._pending_hero
        self._pending_fight = self._pending_hero = None
        if fight is not None:
            self.selectFightRequested.emit(fight)
        if hero is not None:
            self.highlightHeroRequested.emit(hero)

    @Slot(int)
    def fightSelected(self, number: int) -> None:
        """The user picked a fight in the figure."""
        self.fight_selected.emit(number)

    @Slot(str)
    def heroFollowed(self, hero: str) -> None:
        """The user followed a hero in the figure."""
        self.hero_followed.emit(hero)

    @Slot(bool, bool, str, float, float, float)
    def playbackChanged(
        self,
        available: bool,
        playing: bool,
        clock: str,
        seconds: float,
        duration: float,
        speed: float,
    ) -> None:
        """The figure's player changed (reported only when something differs)."""
        self.playback_changed.emit(available, playing, clock, seconds, duration, speed)

    @Slot(int)
    def openFight(self, number: int) -> None:
        """A link in a figure pointed at fight ``number`` (e.g. ``#fight-6``)."""
        self.fight_requested.emit(number)
