# Task: Build a hybrid desktop app for gem (PySide6 shell + embedded Astro figures), shipped as a Windows installer

## Goal
Build a desktop viewer for gem (Dota 2 replay parser, `gem-dota` on PyPI) that reuses the existing Astro docs-site figures instead of rewriting them in Qt. The native PySide6 app handles the shell, parsing and tables. The existing figures (fight player, objectives, lanes, runes, lead, wards) run unchanged in `QWebEngineView`.

**End goal:** a user downloads one `GemStudio-Setup-<version>.exe`, runs it, and uses the app. They install **no** Python, Node or other tools. See "Distribution".

## Decisions made (override anything below that conflicts)
- **Separation:** all new code lives in `app/`. Never edit `src/gem/` (engine), `site/`, the root `pyproject.toml`, `CHANGELOG.md` or `CLAUDE.md`. Upstream (`whanyu1212/gem-dota`) must merge into this fork without conflicts, so the engine and site can be upgraded whenever upstream releases.
- **Figures are built from `site/` in place, with no copies.** `app/web` has its own Vite config that imports `site/src/lib/*.ts`, `site/src/figures/*.ts` and the site CSS directly, with its own entry pages and a data loader. Vite is only a build tool (it compiles TypeScript/CSS to static files); it does not run inside the app.
- **PySide6 shell with `QWebEngineView`** (not pywebview).
- **Dashboard screen ("Dashboard-Gem") is designed in Stitch** (project `18090275263856862448`) and **rebuilt as native Qt widgets** with a QSS stylesheet taken from the design's colours, type and spacing. The figures stay web content.
- **"Analytical Telemetry"** is a collapsible bottom dock with a toggle, holding the native tables and time series (gold, XP, HP, positions, combat log) built from `gem.parse_to_dataframe`.
- PySide6 lives in `app/pyproject.toml`, not in the root project. `pip install gem-dota` is unaffected.

## Constraints (read CLAUDE.md first)
- Project uses `uv`. Run `uv run pytest`, `uv run ruff check src/ tests/`, `uv run mypy src/gem/` to confirm the engine side is unaffected; the app has its own lint/tests under `app/`.
- Don't touch the parser, extractors or generated protobufs.
- gem presents facts, not interpretation. Don't add tags, scores or verdicts.
- Use Google-style docstrings on public functions. Never run Bash commands in the background.
- The docs site must keep building as before (`cd site && npm run build && npm run check-urls && npm run check-links && npm test && npm run check`). Since `site/` is not edited, this is a regression check only.
- Do not commit large replay files. Use the fixtures under `tests/fixtures/`.
- Don't commit secrets (e.g. the Stitch API key lives in the local Claude config only).
- `CHANGELOG.md` is not edited (engine file). Keep an `app/CHANGELOG.md` for the app.

## Architecture
```
PySide6 main window (Python)
├─ Native sidebar / header: replay open, match info, player filters
├─ Dashboard (native Qt widgets, from the Stitch design)
├─ QWebEngineView: figures (fights + player, objectives, lanes, runes, lead, wards)
│     loads app/web/dist/ via a custom URL scheme  (compiled once at build time)
└─ Analytical Telemetry dock (bottom, toggle): QTableView / pyqtgraph
        ▲  QWebChannel (small messages only: ids, ticks, selections)  ▲
Bulk figure data: Python writes JSON files, figures load them by URL.
```

### Repository layout
```
app/
  pyproject.toml          own project; depends on gem-dota (pinned range) + PySide6
  gemstudio/              Python package (shell, jobs, exporter, bridge, models)
  web/                    Vite project (build config, entry pages, data loader, drift test)
    vite.config.ts        aliases into ../../site/src
    dist/                 build output (gitignored)
  tests/
  packaging/              PyInstaller spec, Inno Setup script, icons, license collation
  scripts/                build_app.ps1, check_figure_inputs.py
```

## Phase 0: Investigate (DONE; findings)
- Only `site/src/lib/docs.ts` imports an Astro API (`astro:content`); no figure code does. Figures are plain TypeScript + DOM/SVG + Vite features, so they can be built outside Astro.
- Each figure has two halves: `site/src/figures/<name>.ts` (build-time markup as strings, statically imports committed JSON) and `site/src/lib/<name>-figure.ts` (`mount<Name>Figure(el, data)`, takes data as an argument). `DocLayout.astro` wires them with `import("../data/x.json")`.
- Data files (`site/src/data/`): `home.json` (match, players, map overlay), `fights/index.json` + `fights/<n>.json`, `fight.json` (home page Figure 3), `lanes.json`, `lead.json`, `objectives.json`, `runes.json`, `wards.json`.
- Static imports of those JSON files are the only barrier to runtime data. `lib/fights-figure.ts` also uses `import.meta.glob` for per-fight files and for hero/item icons, which bakes data into a bundle.
- All JSON is produced by `scripts/export_site_home_data.py` (`fights_recipe`, `objectives_recipe`, `lead_recipe`, `lanes_recipe`, `runes_recipe`, `wards_recipe`, `map_overlay`, each taking a `ParsedMatch`). It loads the recipes from `examples/cookbook/*.py` by file path, and objectives/fights need a second pass over the replay for building positions (`load_map_places`). None of it is in the `gem-dota` wheel.
- Icons in `site/src/assets/icons/` are fetched by `scripts/fetch_hero_icons.py` / `fetch_item_icons.py`, not committed.
- Not yet verified: that the figures actually build and render outside Astro (Phase 1 proves it).

## Phases (stop and report after each one)

### Phase 1: Figures build from `site/` in place (fights first)
1. Create `app/web` (Vite, TypeScript). Point `resolve.alias` / `server.fs.allow` at `../../site/src` so lib, figures, styles and fonts are imported in place.
2. Write a Vite plugin that answers the committed-JSON imports (`../data/*.json`) with runtime data: JSON located by `?data=<url>` (or `window.gemData`), falling back to the committed JSON for development. It also neutralises the `import.meta.glob` data/icon globs in `fights-figure.ts` with a pattern replace, **and a test fails loudly if upstream changes those lines**.
3. Write the fights entry page (`fights.html`): create the figure shell, call the build-time markup function and `mountFightsFigure`. Prove it builds and renders from fixture-derived JSON.
4. Expose a small JS API on `window` (`gemFigure.seek(tick)`, `gemFigure.highlightPlayer(id)`, `gemFigure.selectFight(n)`) with events back out (`fightSelected`, `tickChanged`). Wrap, don't edit, the site code; if the site has no hook for a call, list it as a gap instead of patching `site/`.
5. Verify `site/` is untouched (`git status`) and still builds.

### Phase 2: Minimal Qt shell (DONE; see `app/README.md`)
Built: `app/gemstudio` (window, `gem://` scheme handler, parse worker process, pre-check, cache), 23 tests (18 unit, 5 offscreen Qt). Finding: `gem.parse()` does not raise on a bad header; it returns a placeholder match with `parse_error` set, so the worker treats "error with `truncated_at_tick == 0`" as a failed replay. The figure still shows the site's committed demo data until Phase 3.
1. `app/gemstudio` with a `QMainWindow` and a `QWebEngineView` loading `app/web/dist`.
2. Serve `dist/` through a `QWebEngineUrlSchemeHandler` (custom scheme, e.g. `gem://app/`). Plain `file://` breaks module scripts and fetch. A loopback server was the alternative; the scheme handler is preferred for the installed app because it needs no port and no firewall prompt. Document the choice.
3. File-open and drag-drop for `.dem`. Parse with `gem.parse()` in a worker (QThread/process) with a progress signal. Never block the UI thread; the engine has no progress callback, so single files show an indeterminate indicator.

#### Parsing in the installed app
The frozen app parses with the same `gem.parse()` as the CLI, inside the embedded Python runtime.
- **Entry routes (all lead to one parse job):** File → Open (`*.dem`), drag-and-drop, double-click / "Open with" via the optional `.dem` association (path arrives as a command-line argument), and match-ID download (`fetch_replay`, which decompresses `.bz2`/zstd to `.dem`).
- **Pre-check:** the parser validates the first 8 bytes (`PBDEMS2\0`) and raises `ReplayDataError` otherwise. The app also rejects a wrong extension or an empty file first.
- **Worker process:** parse in a separate process (`multiprocessing`; call `multiprocessing.freeze_support()` at startup, required for frozen Windows builds). The UI shows a busy indicator and Cancel (terminates the worker). The worker writes the figure JSON (Phase 3) and a cached `to_json` copy to `%APPDATA%`, and returns only paths and a short summary, never the whole `ParsedMatch`.
- **Cache:** keyed by file hash + engine version; reopening uses `load_json`. A new engine version invalidates it.
- **Errors:** truncated/corrupt replay keeps partial data and sets `ParsedMatch.parse_error` / `truncated_at_tick` (show a warning banner). Wrong file: friendly message with a "copy details" button. Non-data bugs propagate from the engine; the worker catches them, shows a generic failure and logs the traceback to `%APPDATA%`. Download failures are reported separately.
- **To verify in the frozen build:** native modules (`python-snappy`, `zstandard`, `protobuf`) load from the bundle, and measure time and memory on the truncated fixture and a full replay before fixing UI messages or size limits.

### Phase 3: Python exporter (DONE; see `app/gemstudio/export.py`, `jobs.py`)
Built: the exporter reuses the site script's functions by path (no copy) and writes a per-replay folder served at `gem://app/_data/`; the job runs the parse and two replay passes (hero states, map places) **in parallel**, then the export, all cached. Measured on a real 36-min, 70 MB replay: parse 165 s, each pass about 125 s, export about 48 s, so a cold open is about 3.5 min and later opens are instant. Fixed on the way: aliased `@site/...` JSON imports were being bundled as demo data (now a build-time guard fails if any site data is bundled); icons for all 127 heroes and 409 items are bundled at build time (`app/scripts/collect_icons.py`). Tests: 26 fast + 1 slow shape-contract test against the site's committed data. Figures other than fights follow in Phase 5.

### Phase 3 (original text)
1. `app/gemstudio/export.py`: given a `ParsedMatch` and the replay path, write the per-figure JSON into a cache directory in the schema the figures expect. **Reuse** the functions in `scripts/export_site_home_data.py` by importing them from a resolved path; do not copy the logic. In the frozen app these files are bundled as data (see Distribution) and located via a path helper.
2. Pin the contract: a test lists the keys each figure reads and the keys the exporter writes (drift check).
3. Point the web view at the cache directory through `?data=`.
4. Tests for output shape using the truncated committed fixture.

### Phase 4a: Dashboard-Gem and loading view (DONE; see `app/gemstudio/dashboard.py`, `theme.py`, `loading.py`)
Built in Material Telemetry Dark (the user's choice): top bar, five section tabs (only the first is live), a 256 px roster rail, a facts strip, the figure's web view, and the **Analytical Telemetry** bottom drawer (Gold and XP advantage chart, Players table, Fights table). The loading view lists each parallel step's state with an elapsed timer and promises no percentage (the engine reports none). Facts only: the mock's interpretive labels were left out. A row picked in the Fights table opens that fight in the figure. 51 fast tests.

### Phase 4b: Bridge (DONE; see `app/gemstudio/bridge.py`, `app/web/src/bridge.ts`)
Built and verified: both directions for fights (table row and figure) and heroes (roster and figure), no echo loop, pre-load commands kept. Also native playback controls (`app/gemstudio/transport.py`: play/pause, 10 s steps, seek slider, speed chips, Space and Ctrl+Left/Right) mirroring the figure's player. Original text below.

### Phase 4b (original text): Bridge and Dashboard
1. `QWebChannel` with a Python `QObject`: slots `selectFight(n)`, `seekTick(t)`, `highlightPlayer(id)`; signals for events coming back from JS.
2. Two-way demo: click a fight in the figure selects a row in a native `QTableView`; selecting a player in the table highlights them in the figure. Use `QAbstractTableModel` over the DataFrames from `gem.parse_to_dataframe`.
3. Dashboard-Gem screen: pull the design from Stitch (needs the Stitch MCP in a fresh session), derive the QSS theme, build the native dashboard (scoreboard, advantage chart, key stats).
4. Analytical Telemetry bottom dock with its toggle.

### Phase 5: Remaining figures (DONE; each figure in its own tab, see `app/gemstudio/figures.py`)
Built and verified on the real replay: objectives, lanes, runes, lead and wards pages; lazy web views per tab; fight links redirect to the Fights tab; an app-level guard for the lead figure on empty data. Original text below.

### Phase 5 (original text): Remaining figures
Convert objectives, lanes, runes, lead and wards the same way, one at a time, as tabs or a dock layout.

### Phase 6: Packaging and installer (BUILT; signing decision open, see `Implementation_log.md` Step 15)
The build, self-test and installer work (`app/scripts/build_app.ps1`). Unsigned builds can be blocked by Windows 11 Smart App Control; a trusted code-signing identity is needed before sharing the exe. Original text below.

### Phase 6 (original text): Packaging and installer (see Distribution)
Build pipeline, PyInstaller bundle, Inno Setup installer, clean-machine test, CI release workflow.

## Distribution: how users get a `.exe` with nothing else installed

### Who needs what
| | Python | Node | Qt/Chromium | Internet |
|---|---|---|---|---|
| **End user** | no (embedded) | no (figures are precompiled) | no (bundled) | only to download replays by match ID, and to fetch icons if not bundled |
| **Build machine / CI** | yes (3.12 + `uv`) | yes (Node 22+; for `npm ci`, Vite and the icon scripts) | pulled in by PySide6 | yes |

Python's interpreter ships inside the installer (PyInstaller). Node is used only to compile the figures; its output (`app/web/dist/`) is static HTML/JS/CSS.

### Build pipeline (script: `app/scripts/build_app.ps1`; the same steps run in CI)
1. `uv sync` in `app/` (installs the pinned `gem-dota`, PySide6, PyInstaller).
2. `cd site && npm ci` (needed for fonts and shared deps), then fetch hero/item icons with the repo's two fetch scripts (cached).
3. `cd app/web && npm ci && npm run build` produces `dist/`.
4. PyInstaller (one-folder mode) with a spec file in `app/packaging/`. Bundles: Python runtime, `gem-dota` and its native deps (`python-snappy`, `zstandard`, `protobuf`, `numpy`, `pandas`, `pyarrow`), PySide6 with QtWebEngine, `app/web/dist`, `gem/data/*.json`, `scripts/export_site_home_data.py`, `examples/cookbook/*.py`, icons, license files.
5. Inno Setup compiles the folder into `GemStudio-Setup-<version>.exe`: per-user install (no admin rights), Start-menu shortcut, uninstaller, optional `.dem` file association.
6. Smoke test: launch the frozen app on a clean Windows install (Windows Sandbox or a VM), open the fixture replay, check that the figure renders and an export works.
7. Publish the installer as a GitHub Release asset on a version tag (GitHub Actions, `windows-latest`).

### Things to get right
- **QtWebEngine:** needs `QtWebEngineProcess.exe`, its resources and locale files in the bundle; PyInstaller has PySide6 hooks, but verify. It also makes the app large. Estimate (to be measured): several hundred MB unpacked, roughly 150-300 MB as an installer.
- **Native packages:** `python-snappy`, `zstandard` and `protobuf` are the likeliest to break a frozen build. Test them first, in the Phase 6 spike or earlier.
- **Repo-relative paths:** `export_site_home_data.py` computes paths from its own location (`REPO_ROOT`, a `src` path insert, the `examples/cookbook` folder). The app's wrapper must resolve these for both the dev tree and the frozen bundle (`sys._MEIPASS`) without editing the script.
- **Data location:** app data (cache, settings, downloaded replays) goes in `%APPDATA%`/`%LOCALAPPDATA%`, never the install folder.
- **Icons:** fetched by the repo's scripts from external sources; decide at Phase 6 whether to bundle them or download on first run, and check Valve's terms.
- **Updates:** v1 is manual (download the new installer). Later: a version check against GitHub Releases.
- **Signing:** unsigned installers trigger Windows SmartScreen warnings. Plan a code-signing certificate before wide distribution.
- **Versioning:** the app has its own version and shows the bundled engine version (e.g. `Gem Studio 0.1.0, engine gem-dota 0.13.0`). Upgrading the engine means: merge upstream, bump the pin, run the contract/drift tests, rebuild.
- **Licensing:** include gem's MIT licence and `THIRD_PARTY_LICENSES`; PySide6/Qt is LGPL (dynamic linking in a one-folder build is the safe route; include the notices) and Chromium's notices ship with QtWebEngine; confirm terms for Dota 2 icons and the map image.
- **Alternatives to PyInstaller** if it gives trouble: Nuitka, or `briefcase`. The Inno Setup step stays the same.

## Acceptance criteria
- The docs site is unchanged in behaviour and `git diff` shows no edits under `src/gem/`, `site/`, root `pyproject.toml`, `CHANGELOG.md`.
- The app opens a `.dem` file, parses it off the UI thread with progress, and shows the fight player with correct data.
- Selecting in the native table and in the figure stays in sync through the bridge.
- Dashboard-Gem matches the Stitch design; the Analytical Telemetry dock toggles at the bottom.
- PySide6 stays out of the root project. `pip install gem-dota` is unaffected.
- A user installs `GemStudio-Setup-<version>.exe` on a clean Windows machine with no Python or Node, and the app opens, parses the fixture replay and renders the figures.
- No parser changes.

## Process
Work phase by phase. At the end of each phase, summarize what changed, the commands run and their results, and any open questions. Ask before starting the next phase.
