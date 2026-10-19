# UI layer plan: isolated from the gem engine

Goal: a local desktop app and Windows installer built on gem, where upstream
changes to the parser (`whanyu1212/gem-dota`) never conflict with the UI code.

## Principles

1. **Additive only.** All UI code lives in new top-level paths. Never edit
   `src/gem/`, `tests/`, `site/`, `scripts/`, `CHANGELOG.md`, `pyproject.toml`
   (root) or `CLAUDE.md`. Then `git merge upstream/main` has nothing to conflict on.
2. **Depend on gem as a library**, through its public API (`gem.__all__`) only.
   No imports from `gem.parser`, `gem.extractors`, `gem.schema`, etc.
3. **One adapter module** (`engine.py`) is the only file in the UI that imports
   `gem`. Every API change is absorbed there; screens never see gem types.
4. **Pin the engine, upgrade deliberately.** The app ships a tested gem version;
   upgrading is a conscious step guarded by contract tests.

## Repository layout

```
gem-dota-uI/                  (fork; upstream remote = whanyu1212/gem-dota)
├── src/gem/ ...              untouched engine (tracks upstream)
└── app/                      NEW: everything of yours lives here
    ├── pyproject.toml        own project: name "gem-studio", depends on gem-dota
    ├── gemstudio/
    │   ├── engine.py         ONLY file importing gem (adapter + view models)
    │   ├── jobs.py           worker process/thread, progress, cancel
    │   ├── cache.py          parsed-JSON cache keyed by (file hash, gem version)
    │   ├── settings.py       user config in %APPDATA%
    │   └── ui/               screens/widgets (framework TBD)
    ├── tests/
    │   ├── test_contract.py  asserts the gem API/tables the UI relies on
    │   └── test_engine.py
    ├── packaging/            PyInstaller spec, Inno Setup script, icons
    └── scripts/              build_installer.ps1, sync_upstream.ps1
```

Fork already has the layout needed: root project = engine, `app/` = product.

## Engine dependency: two options

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. PyPI pin (recommended)** | `app/pyproject.toml`: `gem-dota>=0.13,<0.14` | Clean separation; upgrades are a version bump; installer built from a released wheel | Cannot use unreleased upstream fixes |
| B. Path/git dependency | `gem-dota @ file:..` or git ref | Test against fork/upstream `main` | Couples app to repo state; fixes arrive unreviewed |

Use A for releases. Use B in a dev environment/CI job ("canary") to see breakage early.

## Contract layer (the key to surviving upstream changes)

`engine.py` exposes a small stable surface to the UI, e.g.:

- `open_replay(path) -> MatchView`
- `download_replay(match_id, dir) -> Path`
- `export(path, fmt, include, out)`; `batch(sources, out, workers, recursive, include)`
- `list_tables(include) -> list[str]`

`MatchView` is the app's own dataclass (scoreboard rows, advantage series,
event lists) built from `ParsedMatch` in one place. Prefer DataFrames
(`gem.parse_to_dataframe`) for tables: their schema is documented as fixed
and versioned, so they are the most stable surface. `to_json` carries
`SCHEMA_VERSION`; check it.

`tests/test_contract.py` runs against the committed truncated fixture
(`tests/fixtures/ti14_finals_g3_xg_vs_falcons_truncated.dem`) and asserts:
tables in `CORE_TABLES`/`OPTIONAL_GROUPS` exist, columns the UI reads exist,
`gem.__all__` contains the functions used, CLI flags unchanged. A failure
tells you exactly which upstream change broke which screen.

## Staying in sync with upstream

- Fork `main` mirrors `upstream/main`: `git fetch upstream && git merge upstream/main`
  (or `git pull upstream main`). Conflicts are impossible if you only add `app/`
  and `docs/ui/`. Keep your UI commits out of engine files.
- Upstream already watches its own pins; read `CHANGELOG.md` `[Unreleased]` on each merge.
- Deprecations: gem has a `_deprecation` layer that warns before removal
  (0.12 deprecated, 0.13 removed). Run the app tests with
  `-W error::DeprecationWarning` in CI to learn early.
- Optional CI: scheduled job that merges `upstream/main` into a temp branch,
  installs it, runs `app/tests`. Red = look before upgrading the pin.
- Do not fix engine bugs in the fork. Report or PR them upstream, then bump the pin.

## Framework choice (decide before building)

| Option | Fit |
|---|---|
| **PySide6 (Qt)** | Native, one Python process, good tables/charts (Qt Charts / pyqtgraph), PyInstaller-friendly. Simplest packaging. |
| **Web UI in a shell** (FastAPI + React, wrapped with pywebview/Tauri/Electron) | Best-looking charts/design output from Claude Design; needs a local server + sidecar packaging. |
| Streamlit/NiceGUI | Fastest prototype; weaker as an installed desktop product. |

Claude Design outputs web tech (HTML/CSS/React), so a **web UI + pywebview**
(Python backend in-process, local HTTP/JS bridge) reuses its designs directly
and still ships as one `.exe`. Recommended unless you prefer native Qt.

## Concurrency and robustness

- Parse in a **separate process** (`multiprocessing`/`concurrent.futures`):
  parsing is CPU-bound and blocking, with no progress callback. UI shows
  indeterminate progress for single files, real progress for batch
  (`parse_many`).
- Cancel = terminate the worker process.
- Surface `parse_error` / `truncated_at_tick` to the user instead of failing.
- Cache parsed JSON per (replay hash, gem version) so reopening is instant;
  invalidate when the engine version changes.
- Network only for match-ID download; make it explicit and failure-tolerant.

## Installer

1. **Bundle**: PyInstaller (one-folder) from `app/` with gem-dota installed
   from the pinned wheel. Include `gem/data/*.json` (use `collect_data_files("gem")`)
   and `pyarrow` (Parquet export). Test `python-snappy`, `zstandard` and
   `protobuf` native bits early on a clean Windows VM: highest-risk step.
2. **Installer**: Inno Setup (`.exe` setup, Start-menu shortcut, uninstaller,
   `.dem` file association optional). Per-user install avoids admin rights.
3. **Icons**: not shipped in gem. Either bundle the output of
   `scripts/fetch_hero_icons.py`/`fetch_item_icons.py` (check licensing/terms of
   the source) or download on first run into `%APPDATA%`.
4. **Versioning**: app version independent of gem (`gem-studio 0.1.0 (engine
   gem-dota 0.13.0)`), engine version shown in "About".
5. **CI**: GitHub Actions on `windows-latest` builds installer on tag, runs
   contract tests first. Code-sign later (unsigned installers trigger SmartScreen).
6. **Updates**: v1 manual download; later a version check against GitHub releases.

## Phases

1. **Foundations**: `app/` skeleton, `engine.py` adapter, contract tests, CLI-parity jobs (parse, export, batch).
2. **Prototype UI**: open replay → scoreboard + gold/XP advantage + export screen (use `docs/ui/data-reference.md` as the Claude Design brief).
3. **Explorers**: player detail, events (fights, wards, runes, draft), settings, cache.
4. **Packaging**: PyInstaller build, clean-VM test, Inno Setup installer, CI.
5. **Hardening**: error states, truncated replays, upgrade-pin routine, docs.

## Licensing

gem is MIT (keep its LICENSE and `THIRD_PARTY_LICENSES` in the installer).
Dota 2 names/art belong to Valve; confirm icon use before distributing.
