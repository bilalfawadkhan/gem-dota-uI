"""The ``gem://`` URL scheme: how the web view loads the figures and their data.

Plain ``file://`` pages cannot use module scripts or ``fetch``, and a loopback
server needs a port and can trigger a firewall prompt. A custom scheme handled in
the app needs neither. One host serves both, so figure pages and data are
same-origin and need no CORS:

- ``gem://app/<file>``: the compiled figures (``app/web/dist``),
- ``gem://app/_data/<file>``: the data folder of the open replay (``fights/7.json``,
  ``figures/map.webp``, ...).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QBuffer, QByteArray, QFile, QIODevice, QObject
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineUrlRequestJob,
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
)

SCHEME = b"gem"
HOST = "app"
DATA_PREFIX = "/_data/"
DEFAULT_PAGE = "fights.html"
#: Qt's QWebChannel client script lives in Qt's resources; the page loads it from here.
CHANNEL_SCRIPT_PATH = "/qwebchannel.js"
CHANNEL_SCRIPT_RESOURCE = ":/qtwebchannel/qwebchannel.js"

_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}


def register_scheme() -> None:
    """Register ``gem://``. Must run before the ``QApplication`` is created."""
    scheme = QWebEngineUrlScheme(QByteArray(SCHEME))
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.CorsEnabled
        | QWebEngineUrlScheme.Flag.FetchApiAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)


def channel_script() -> bytes | None:
    """Qt's ``qwebchannel.js`` from its resources, or None if QtWebChannel is not loaded."""
    resource = QFile(CHANNEL_SCRIPT_RESOURCE)
    if not resource.open(QIODevice.OpenModeFlag.ReadOnly):
        return None
    try:
        return bytes(resource.readAll().data())
    finally:
        resource.close()


def content_type(path: Path) -> str:
    """The MIME type to serve a file with (module scripts need a JavaScript type)."""
    return (
        _TYPES.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or ("application/octet-stream")
    )


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def resolve_request_path(url_path: str, web_dir: Path, data_roots: list[Path]) -> Path | None:
    """Map a request path to a file, refusing anything outside the served folders.

    Args:
        url_path: The URL's path, e.g. ``/fights.html`` or ``/_data/fights/7.json``.
        web_dir: The compiled figures folder.
        data_roots: The open replay's data folders, searched in order.

    Returns:
        The file to serve, or None when it does not exist or escapes its folder.
    """
    path = unquote(url_path)
    if path.startswith(DATA_PREFIX):
        roots, relative = data_roots, path[len(DATA_PREFIX) :]
    else:
        roots, relative = [web_dir], path.lstrip("/") or DEFAULT_PAGE
    for root in roots:
        candidate = (root / relative).resolve()
        if _inside(root, candidate) and candidate.is_file():
            return candidate
    return None


class GemSchemeHandler(QWebEngineUrlSchemeHandler):
    """Serves ``gem://app/...`` from the figures folder and the open replay's data."""

    def __init__(self, web_dir: Path, data_roots: list[Path], parent: QObject | None = None):
        super().__init__(parent)
        self.web_dir = web_dir
        self.data_roots = data_roots

    def set_data_roots(self, roots: list[Path]) -> None:
        """Point ``/_data/`` at a different replay's data."""
        self.data_roots = roots

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:  # noqa: N802 (Qt override)
        """Answer one request: the file's bytes, or a not-found error."""
        url = job.requestUrl()
        if url.host() == HOST and url.path() == CHANNEL_SCRIPT_PATH:
            script = channel_script()
            if script is None:
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            buffer = QBuffer(job)
            buffer.setData(script)
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            job.reply(QByteArray(b"text/javascript"), buffer)
            return
        file = (
            resolve_request_path(url.path(), self.web_dir, self.data_roots)
            if url.host() == HOST
            else None
        )
        if file is None:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        buffer = QBuffer(job)
        buffer.setData(file.read_bytes())
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(QByteArray(content_type(file).encode()), buffer)


def install(profile: QWebEngineProfile, handler: GemSchemeHandler) -> None:
    """Attach the handler to a web profile."""
    profile.installUrlSchemeHandler(QByteArray(SCHEME), handler)
