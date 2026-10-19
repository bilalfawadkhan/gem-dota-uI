# Gem Studio (desktop app)

A PySide6 shell around the `gem` replay parser. The docs site's figures run unchanged in
a `QWebEngineView` (built by `app/web`, read in place from `site/`). Everything here is
additive: the engine (`src/gem`) and the docs site are never edited, so upstream can be
merged at any time. Plan: `../UI-Implementation-plan.md`. Design notes: `design/`.

## Develop (Windows, no `uv` needed)

```powershell
cd app
python -m venv .venv
.\.venv\Scripts\python -m pip install numpy pandas protobuf python-snappy rich zstandard pyarrow PySide6 pytest ruff mypy
# Use the fork's engine source so the app, the repo scripts and the fixtures agree:
echo D:\path\to\gem-dota-uI\src > .venv\Lib\site-packages\gem_fork.pth
# Icons (downloaded by the repo's scripts, not committed), then the figures:
.\.venv\Scripts\python ..\scripts\fetch_hero_icons.py; .\.venv\Scripts\python ..\scripts\fetch_item_icons.py
.\.venv\Scripts\python scripts\collect_icons.py
cd web; npm install; npm run build; cd ..     # -> web/dist
.\.venv\Scripts\python -m gemstudio [replay.dem]
```

With `uv`: `uv sync --group dev` in `app/` installs `gem-dota` from PyPI (pinned range in
`pyproject.toml`) instead of the fork's source.

## Test

```powershell
.\.venv\Scripts\python -m pytest         # unit + offscreen Qt shell tests (needs web/dist)
.\.venv\Scripts\python -m pytest -m slow tests/test_export.py   # real replay in the repo root (minutes when cold)
.\.venv\Scripts\ruff check gemstudio tests; .\.venv\Scripts\ruff format gemstudio tests
.\.venv\Scripts\mypy gemstudio
cd web; npm test                          # figure-build plugin tests
```

Qt's `offscreen` platform has no fonts, so native text shows as boxes in offscreen
screenshots; that is a harness artifact. The shell tests check the web content and
behaviour, not native text.

## How it fits together

| Module | Role |
|---|---|
| `gemstudio/__main__.py` | entry; calls `multiprocessing.freeze_support()` (needed in a frozen build) |
| `figures.py` | one web view per figure tab (`FigurePage`: view + its bridge + a JavaScript error log), created when first shown and reloaded for a new replay |
| `window.py` | main window: top bar, section tabs, and three pages (empty, loading, dashboard); Open via menu, button, drag-and-drop or command line |
| `theme.py` | Material Telemetry Dark (from the Stitch design): palette + QSS; font fallbacks (Roboto Flex / JetBrains Mono are not bundled yet) |
| `dashboard.py` | the Dashboard-Gem screen: roster rail, facts strip, the figure's web view, and the **Analytical Telemetry** drawer (Gold & XP chart, Players and Fights tables) |
| `loading.py` | the loading view: each step's state, elapsed time, Cancel; no invented percentage or time left |
| `models.py` | table model over plain dicts (the UI process never imports pandas) |
| `dashboard_data.py` | the facts the dashboard shows, written as `dashboard.json` by the export (no verdicts) |
| `precheck.py` | refuses a wrong file (extension, empty, `.bz2`, bad header) before any parse |
| `jobs.py` | runs parse + hero-states pass + map-places pass as **separate processes in parallel**, then the export; a 100 ms timer polls their queues, so the UI never waits; Cancel terminates all |
| `worker.py` | Qt-free steps run in worker processes: `gem.parse`, cache (`%LOCALAPPDATA%\GemStudio\cache`, keyed by file hash + engine version), error mapping |
| `export.py` | writes the figure data folder from the cached match, reusing `scripts/export_site_home_data.py` by path; the two replay passes it needs |
| `scheme.py` | the `gem://app/` URL scheme that serves `web/dist`, the replay's data (`/_data/`) and Qt's `qwebchannel.js` |
| `transport.py` | native playback controls above the figure (play/pause, -10 s/+10 s, seek slider, clock, speed chips; Space and Ctrl+Left/Right) mirroring the figure's player |
| `bridge.py` | the `gem` object on the page's QWebChannel: ids, names and seconds only; keeps commands sent before the page connects |
| `paths.py` | dev vs. frozen locations |

### Why a custom URL scheme

`file://` breaks module scripts and `fetch`; a loopback server needs a port and may raise a
firewall prompt. A `QWebEngineUrlSchemeHandler` needs neither, and one host for pages and
data keeps them same-origin (no CORS). Paths are resolved inside the served folders only.

### What `gem.parse` does with bad files

It does **not** raise on a wrong header or a damaged start: it records `parse_error` and
returns a placeholder match (10 players, no heroes). The worker treats "error and nothing
read (`truncated_at_tick` is 0)" as a failed replay and anything that read further as a
partial one (warning in the status bar).

## Timing (one real replay: 36 min, 70 MB)

| Step | Time |
|---|---|
| parse (`gem.parse`) | about 165 s |
| hero-states pass, map-places pass | about 125 s each, in parallel with the parse |
| write figure data | about 48 s |
| **first open** | about 3.5 min |
| reopen (cache) | a few seconds |

The loading view says this to the user (it is in `loading.py`): the first open takes a few
minutes and the result is saved. Update that sentence if the timings change.

## Run it

```powershell
cd app
.\.venv\Scripts\python -m gemstudio                       # empty window; use Open replay...
.\.venv\Scripts\python -m gemstudio ..\9045456575_334166624.dem
```

After changing anything under `app/web` or `site/`, rebuild the figures first (`cd web; npm run build`).

## Build the installer

```powershell
cd D:\Repo\gem-dota-uI
powershell -File app\scripts\build_app.ps1            # about 7.5 min
# optional: -Replay <full .dem> to self-test with a full replay; -SkipWeb; -SkipInstaller; -PfxPath cert.pfx
```

It builds the figures, bundles the app with PyInstaller (`app\build\dist\GemStudio`, 583 MB), runs the frozen
app's **self-test** with no Python on the PATH and an empty data folder, and only then compiles the installer
with Inno Setup (`app\build\installer\GemStudio-Setup-<version>.exe`, about 167 MB). Needs the venv with
`pip install -r requirements-build.txt`, Node 22+ and Inno Setup 6 (`winget install JRSoftware.InnoSetup`).
End users need none of these. Check any build by hand with `GemStudio.exe --self-test some.dem`.

**Unsigned builds and Windows 11.** Smart App Control (on by default on clean Windows 11 installs) blocks
unsigned programs and libraries it has no reputation for, with no "run anyway" button, and SmartScreen warns
about unsigned installers. This was seen on this machine (Windows' Code Integrity log, events 3077/3033). Sign the
build with a trusted code-signing certificate (`-PfxPath`; see `scripts\sign_files.ps1`) before sharing it.

## Build it on GitHub and publish a download

`.github/workflows/gem-studio-installer.yml` builds the installer on a Windows runner and can attach it to a
release. It runs only when started by hand or when a tag named `studio-v*` is pushed (merging upstream never
triggers it). **It has not been run on GitHub yet**, so expect to fix small things on the first run.

1. Commit and push the work to your GitHub repository (the `app/`, `.github/`, README changes).
2. Test it first: Actions tab, "Gem Studio installer", **Run workflow**. When it finishes, download the
   `GemStudio-installer` artifact (the installer and the self-test report) from the run page.
3. Publish: `git tag studio-v0.1.0` then `git push origin studio-v0.1.0`. The workflow builds again and attaches
   `GemStudio-Setup-0.1.0.exe` to a release, which the README's "Download the latest installer" link points to.
   Use the app version from `app/gemstudio/__init__.py` in the tag.

## Status

Phases 0-6. The window has a tab for each figure: Fight Replay & Dashboard, Objectives, Lanes, Runes,
Gold & XP Lead and Wards. The roster rail, facts strip and telemetry drawer stay on every tab; the
playback bar belongs to the Fights tab. The figure and the native widgets are linked both ways through a
QWebChannel bridge (`bridge.py`) with native playback controls (`transport.py`); a fight link in another
figure opens that fight in the Fights tab. "Scoreboard & Players" and "Batch & Parquet Export" are disabled
placeholders, and "Fetch ID" (download by match ID) is not built. The installer builds and self-tests (see above); signing is the open item.
