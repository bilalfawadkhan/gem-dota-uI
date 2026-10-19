# PyInstaller spec for Gem Studio (one-folder build, windowed).
#
# Run from app/ (build_app.ps1 does this):
#   pyinstaller packaging/gemstudio.spec --noconfirm --distpath build/dist --workpath build/work
#
# What goes in, and why:
# - the compiled figures (web/), served to the web view as gem://app/;
# - hero icons for the native roster, and the two ward icons the exporter copies;
# - scripts/export_site_home_data.py, examples/cookbook/ and the 7.41 map: the figure exporter
#   loads the site's script and the recipes BY PATH (they are not in the gem-dota package), and the
#   script finds them relative to its own folder, so they keep the repository's layout inside the
#   bundle (scripts/, examples/cookbook/, assets/maps/);
# - gem's own data files (heroes, items, abilities, camp zones, ...);
# - every gem module, because the exporter script and the recipes import gem lazily and are not
#   seen by PyInstaller's analysis.
# Left out: pyarrow (only Parquet export uses it, and that is not in the UI yet) and the other
# large packages the app never imports.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APP = Path(SPECPATH).parent  # app/
REPO = APP.parent
BUILD = APP / "build"

icon = APP / "packaging" / "gemstudio.ico"

datas = [
    (str(APP / "web" / "dist"), "web"),
    (str(APP / "web" / "icons" / "heroes"), "icons/heroes"),
    (str(REPO / "site" / "src" / "assets" / "icons" / "ward_observer.png"), "icons"),
    (str(REPO / "site" / "src" / "assets" / "icons" / "ward_sentry.png"), "icons"),
    (str(REPO / "scripts" / "export_site_home_data.py"), "scripts"),
    (str(REPO / "assets" / "maps" / "Game_map_7.41.jpg"), "assets/maps"),
    (str(BUILD / "LICENSES.txt"), "licenses"),
]
# The recipes, without compiled caches.
for recipe in sorted((REPO / "examples" / "cookbook").glob("*.py")):
    datas.append((str(recipe), "examples/cookbook"))
datas += collect_data_files("gem")

hiddenimports = collect_submodules("gem") + ["pandas", "PIL.Image", "bisect"]

excludes = [
    "pyarrow",
    "tkinter",
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "mypy",
    "ruff",
    "scipy",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtBluetooth",
    "PySide6.QtSql",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
]

a = Analysis(
    [str(APP / "packaging" / "entry.py")],
    pathex=[str(APP)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GemStudio",
    console=False,  # a desktop app: no console window (errors go to the log folder)
    icon=str(icon) if icon.is_file() else None,
    upx=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GemStudio",
)
