"""Cheap checks on a replay path before a parse job starts.

The parser itself validates the Source 2 magic (``PBDEMS2\\0``) and raises
``ReplayDataError``; checking here too means an obviously wrong file is refused
at once, with a message written for the user, without starting a worker.
"""

from __future__ import annotations

from pathlib import Path

MAGIC = b"PBDEMS2\x00"


class ReplayFileError(ValueError):
    """The chosen file cannot be a replay; the message is fit to show the user."""


def check_replay_file(path: str | Path) -> Path:
    """Check that ``path`` looks like a Dota 2 replay.

    Args:
        path: The file the user chose.

    Returns:
        The path as a ``Path``.

    Raises:
        ReplayFileError: If the file is missing, not ``.dem``, empty, compressed
            (``.bz2``), or does not start with the Source 2 replay header.
    """
    file = Path(path)
    if not file.is_file():
        raise ReplayFileError(f"File not found: {file}")
    if file.suffix.lower() == ".bz2":
        raise ReplayFileError(
            "This replay is still compressed (.dem.bz2). Extract it to a .dem file first."
        )
    if file.suffix.lower() != ".dem":
        raise ReplayFileError("Choose a Dota 2 replay file (.dem).")
    if file.stat().st_size == 0:
        raise ReplayFileError("The replay file is empty.")
    with file.open("rb") as handle:
        header = handle.read(len(MAGIC))
    if header != MAGIC:
        raise ReplayFileError(
            "This does not look like a Dota 2 (Source 2) replay: its header is not recognised."
        )
    return file
