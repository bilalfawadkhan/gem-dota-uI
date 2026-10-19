"""Gem Studio: a desktop viewer for gem replays.

The package keeps the Qt-free parts (``paths``, ``precheck``, ``worker``) apart from
the Qt shell so the parse worker, which runs in its own process, never imports Qt.
"""

__version__ = "0.1.0"
