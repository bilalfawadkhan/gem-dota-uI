"""Write ``app/build/LICENSES.txt``: the notices an installed Gem Studio has to carry.

It lists the engine's own licence, the licences of the Python packages bundled in the build (read
from their installed metadata, so it follows what is really in the environment), and the notices for
Qt/PySide6 (LGPL), Chromium, the web fonts and Valve's artwork. It is shown by the installer and
copied into the app's ``licenses`` folder.

This is a good-faith collation for a first build. It is not legal advice, and it does not reproduce
every licence text: have the file reviewed before wide distribution.

Run from ``app/``::

    python packaging/collect_licenses.py
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
OUT = APP / "build" / "LICENSES.txt"

#: Distributions whose files end up in the bundle (names as installed).
BUNDLED = [
    "numpy",
    "pandas",
    "protobuf",
    "python-snappy",
    "cramjam",
    "zstandard",
    "rich",
    "pillow",
    "PySide6",
    "PySide6_Essentials",
    "PySide6_Addons",
    "PySide6_WebEngine",
    "shiboken6",
    "python-dateutil",
    "pytz",
    "tzdata",
    "six",
]

NOTICES = """\
Qt and PySide6
  Gem Studio uses Qt (through PySide6, "Qt for Python") under the GNU Lesser General Public License,
  version 3 (LGPLv3). The Qt libraries are shipped as separate shared libraries (DLLs) next to the
  program and can be replaced with a compatible build. The source code of Qt is available from
  https://download.qt.io/ and of PySide6 from https://code.qt.io/cgit/pyside/pyside-setup.git/ .
  Qt is a trademark of The Qt Company Ltd.

QtWebEngine and Chromium
  The figures are shown with QtWebEngine, which is based on the Chromium project. Chromium and its
  third-party components are under their own licences (BSD-style and others); see
  https://www.chromium.org/ and https://doc.qt.io/qt-6/qtwebengine-licensing.html .

Fonts in the figures
  Inter, Source Serif 4 and JetBrains Mono are used under the SIL Open Font License 1.1
  (https://openfontlicense.org/), as packaged by Fontsource (https://fontsource.org/).

Dota 2 artwork
  Hero and item icons and the minimap image are the property of Valve Corporation. They are used here
  only to display replay data and are not covered by the licences above. Dota 2 and the Dota 2 logo
  are trademarks of Valve Corporation. Gem Studio is not affiliated with or endorsed by Valve.

PyInstaller
  The program is packaged with PyInstaller. PyInstaller's licence (GPL-2.0-or-later with an exception)
  explicitly allows distributing the packaged program under any licence.
"""


def licence_of(name: str) -> tuple[str, str, str]:
    """(version, licence, home page) of an installed distribution, from its metadata."""
    try:
        meta = metadata.metadata(name)
        version = metadata.version(name)
    except metadata.PackageNotFoundError:
        return "(not installed)", "", ""
    licence = meta.get("License-Expression") or ""
    if not licence:
        text = meta.get("License") or ""
        licence = text if text and len(text) < 80 else ""
    if not licence:
        classes = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if "License" in c]
        licence = ", ".join(classes)
    home = meta.get("Home-page") or ""
    if not home:
        for url in meta.get_all("Project-URL") or []:
            home = url.split(",")[-1].strip()
            break
    return version, licence or "see the package", home


def main() -> None:
    """Collate the notices and write them."""
    parts = ["GEM STUDIO: LICENCES AND NOTICES", "=" * 72, ""]
    parts += [
        "Gem Studio is a desktop viewer built on gem (https://github.com/whanyu1212/gem-dota), a Dota 2",
        "replay parser, whose licence follows.",
        "",
        "-" * 72,
        "gem (MIT)",
        "-" * 72,
        (REPO / "LICENSE").read_text(encoding="utf-8").strip(),
        "",
    ]
    third = REPO / "THIRD_PARTY_LICENSES"
    if third.is_file():
        parts += ["-" * 72, "gem's own third-party notices", "-" * 72, third.read_text(encoding="utf-8").strip(), ""]
    parts += ["-" * 72, "Python packages in this build", "-" * 72]
    for name in BUNDLED:
        version, licence, home = licence_of(name)
        if version == "(not installed)":
            continue
        parts.append(f"{name} {version}: {licence}" + (f"  <{home}>" if home else ""))
    parts += ["", "-" * 72, "Other notices", "-" * 72, NOTICES]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
