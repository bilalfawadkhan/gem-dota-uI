# Implementation log: Gem Studio (desktop app on gem)

A running record of what was asked, what was built, how it was checked, and what was decided or
corrected, step by step. Appended after every step until all phases are done. The plan itself is
`UI-Implementation-plan.md`; reference notes are in `docs/ui/` and `app/design/`.

**Conventions.** Dates are 2026-10-16 unless stated. "Verified" means run and observed in this
session, not assumed. Numbers are from this machine (20 cores, 31 GB RAM, Windows 11, Python 3.12).

**Standing decisions** (from the user; they override the plan where they conflict):
- All new code lives in `app/`. Never edit `src/gem/`, `site/`, the root `pyproject.toml`,
  `CHANGELOG.md` or `CLAUDE.md`, so upstream (`whanyu1212/gem-dota`) merges without conflict.
- Hybrid app: PySide6 shell + the docs site's figures in a `QWebEngineView`, built by Vite in
  `app/web` reading `site/src` in place (no copies). Not pywebview.
- Design system: **Material Telemetry Dark** (Stitch project 18090275263856862448).
- "Analytical Telemetry" is a collapsible bottom drawer with a toggle.
- End goal: a Windows installer `.exe`; end users install no Python or Node.
- gem presents facts, not interpretation: no tags, scores or verdicts in the UI.

---

## Step 1: Exploratory search of the codebase

**Asked:** explore the repo to learn the setup and functions, as the basis for a UI and an installer.
**Done:** read `pyproject.toml`, the CLI (`cli.py`), the public API (`api.py`), fetch/batch modules,
the README, and CLAUDE.md.
**Findings:** gem (PyPI `gem-dota`, v0.13.0, MIT) parses Dota 2 `.dem` files offline into a
`ParsedMatch`. CLI: `parse` (summary/json/parquet, `--include analysis|opendota|gold_ledger`) and
`batch` (parallel, parquet). Only network feature: `fetch_replay(match_id)` via OpenDota and the Valve
CDN. No GUI exists. Risks noted: native packages (`python-snappy`, `zstandard`, `protobuf`) for a
frozen build; icons are not shipped; parsing is slow with no progress callback.

## Step 2: Data reference for the UI design, and the isolation plan

**Asked:** list data sources and CLI options for use in Claude Design; then save it and plan how to
add a UI layer that survives upstream engine changes.
**Done:** wrote `docs/ui/data-reference.md` (sources, CLI options, `ParsedMatch`/`ParsedPlayer`
fields, 26 core + optional export tables, design constraints) and `docs/ui/architecture-plan.md`.
**Decisions:** the repo is a fork (`upstream` remote = whanyu1212/gem-dota), so everything new goes
in a new folder and nothing existing is edited; the UI imports gem only through its public API;
contract tests guard the API surface; pin the engine and upgrade deliberately.

## Step 3: The hybrid implementation plan

**Asked:** follow `UI-Implementation-plan.md` (user's own plan: PySide6 shell + Astro figures in
QtWebEngine + QWebChannel); build the dashboard from the Stitch design; ask about ambiguities.
**Questions asked and answers:** Stitch access: user connected the Stitch MCP server (key stored in
the local Claude config only; the key was pasted in chat, so rotate it). Dashboard built as native Qt
widgets. "Analytical Telemetry" = bottom drawer of tables and time series. Site edits: **no**, keep
the UI separate so the engine can be upgraded at any time.
**Changes to the plan:** Phase 1 would have edited `site/` (an embed route); instead the figures are
built from `site/` in place by `app/web`. The optional PySide6 group moved from the root
`pyproject.toml` to `app/pyproject.toml`.
**Distribution clarified:** end users need no Python or Node; both are build-machine tools. The plan
gained a Distribution section (PyInstaller + Inno Setup, build pipeline, risks) and a Phase 6.

## Step 4: Phase 0, investigation (no code changes)

**Findings:** only `site/src/lib/docs.ts` uses an Astro API; figure code is plain TypeScript. Each
figure has a build-time markup half (`site/src/figures/*.ts`, static JSON imports) and a browser half
(`site/src/lib/*-figure.ts`, `mount*Figure(el, data)`). All figure JSON comes from
`scripts/export_site_home_data.py` (functions take a `ParsedMatch`; loads recipes from
`examples/cookbook/` by path; not part of the wheel). Hero/item icons are downloaded, not committed.
**Verdict:** building from `site/` in place works. Vite is only a build tool (compiles TypeScript,
CSS, JSON imports); it does not run in the app.

## Step 5: Phase 1, figures built in place (fights first)

**Built (`app/web`):** Vite config reading `../../site/src`; `plugins/gem-data.ts` (turns the site's
committed-JSON imports into run-time fetches from `?data=`; rewrites the one `FILES` block in
`fights-figure.ts`, and fails the build if upstream changes it); `src/api.ts` (`window.gemFigure`:
`selectFight`, `seekSeconds`, `highlightHero`, `play`, `pause`, events); a dev-only server for the
site's demo data; own `tsconfig.json` (the site's extends Astro's, not installed).
**Verified:** build, 5 plugin tests, `tsc --noEmit` clean, 12 browser checks in Chrome (36 of 36
fights, API methods and events), site files untouched.
**Deviation:** `seekSeconds`, not `seek(tick)`: figures speak in game seconds; tick conversion is
Python's job.
**Later correction:** the "no committed JSON bundled" check used the wrong search string; see Step 9.

## Step 6: Phase 2, the Qt shell and parsing in the installed app

**Asked:** explain how the exe reads and parses a `.dem`, add it to the plan, then build Phase 2.
**Built (`app/gemstudio`):** window, `gem://app/` URL scheme (no port, no firewall prompt, same
origin for pages and data, paths confined to the served folders), pre-check (extension, empty,
`.bz2`, header), parse worker in a separate process (UI polls a queue on a timer), cache keyed by file
hash + engine version, `multiprocessing.freeze_support()` for frozen builds.
**Verified:** 23 tests (18 unit, 5 offscreen Qt), real Windows-platform screenshots.
**Correction:** `gem.parse()` does **not** raise on a wrong header or a damaged start; it records
`parse_error` and returns a placeholder match (10 players, no heroes). Earlier statement that it
raises `ReplayDataError` was wrong. The worker now treats "error and `truncated_at_tick` == 0" as a
failed replay and anything further as partial.
**Environment:** no `uv` on this machine; used `app/.venv` with the fork's `src` via a `.pth` file.

## Step 7: Stitch design pulled

**Asked:** pull the Dashboard-Gem design from Stitch. **Done:** downloaded the screen HTML and a
thumbnail to `app/design/dashboard-gem/` with `README.md` (tokens, layout, mapping to Qt, what the
mock shows that gem cannot or should not).
**Finding:** the project holds two design systems; the screen uses Material Telemetry Dark
(blue `#8ab4f8`, rounded, Roboto Flex), the project default is Obsidian Ancient (gold, sharp, Cinzel).
**Decision (user):** follow Material Telemetry Dark. The mock's interpretive text ("CLIMAX", "Fight
Aggregate Outcome...") is left out; gem presents facts.

## Step 8: Phase 3, exporter (with the user's real replay)

**Input:** `9045456575_334166624.dem` (70 MB, 36 min, 38 fights), excluded from git locally via
`.git/info/exclude`.
**Built:** `export.py` reuses the site script's functions by path (no copy) and writes a per-replay
folder served at `gem://app/_data/`; the job runs the parse and two raw replay passes (hero states,
map places) **in parallel**, then the export; all cached.
**Measured:** parse about 165 s; each pass about 125 s; export about 48 s; first open about 3.5 min;
reopen from cache a few seconds. A raw pass peaks at about 190 MB.
**Verified:** all six figure files have the same shape as the site's committed data; 26 fast tests
plus a slow shape-contract test on the real replay.
**Icons:** all 127 hero and 409 item icons fetched with the repo's scripts and bundled at build time
(`app/scripts/collect_icons.py`). Valve owns them; check terms before redistributing.

## Step 9: Bug found and fixed (demo data had been bundled)

A screenshot showed the figure's top half with the site's demo match and the bottom with the real
one. Cause: imports written with the `@site/...` alias resolved to forward-slash absolute paths that
the plugin's path check rejected, so the demo `fights/index.json` was bundled. My earlier check that
no committed JSON was bundled searched for the wrong string, and the earlier browser tests had been
reading that bundled copy. **Fix:** normalised path handling plus a build-time guard that throws if
any site data file would be bundled; 3 new tests. Verified: the bundle no longer contains the demo
marker, and the figure lists 38 fights from the real replay.

## Step 10: Phase 4a, Dashboard-Gem and loading view

**Asked:** build the dashboard first, add a loading indicator (first open is slow), and send a
sub-agent to find out why.
**Built:** `theme.py` (Material Telemetry Dark palette + QSS, font fallbacks), `dashboard.py` (roster
rail, facts strip, **Analytical Telemetry** drawer with a Gold and XP advantage chart, Players table
and Fights table), `loading.py` (four steps as waiting/running/done, elapsed time, Cancel, no invented
percentage), `models.py`, `dashboard_data.py` (facts written as `dashboard.json`, so the UI never
loads the 66 MB match; the UI process never imports pandas). `jobs.py` gained a per-step state signal.
A row picked in the Fights table opens that fight in the figure.
**Verified:** 51 fast tests; real-platform screenshots of the loading view, the dashboard and each
drawer tab on the real replay; ruff and mypy clean.
**Cosmetic fixes found by looking:** `&` in tab labels (Qt shortcut marker), chip heights, table sort
order (kept in match order until the user sorts), hero names wrapping, chart axis ticks.
**Not done:** Fetch ID button, the four other section tabs (disabled placeholders), bundled fonts.

## Step 11: Sub-agent investigation, why the first open takes about 3.5 minutes

**Result (agent's measurements; not re-run by me, but they match mine):** the critical path is one
pure-Python decode, `gem.parse`, about 175 s; the two other passes finish earlier and cost no wall
time. About 70% of the parse is inherent decode (bare pass 120 s), 30% extractors. After it: 9 s to
save `match.json` and 39 s of export. The engine is already micro-optimised; further gains need
native code (upstream's Rust plan). One pass instead of three was 20 s slower in wall time; keep
three processes.
**App-side speed-ups (ranked):** (1) export from the in-memory match inside the parse process, about
12 s; (2) memoise `build_smoke_analysis` (computed 49 times) and cache the decoded base map, about
17 s (agent patched this: export 39 s to 22 s, `fights/index.json` identical, other files not
diffed); (3) raise the GC threshold in workers, about 15 s; (4) thread-pool the map crops, about 8-10 s.
Estimated first open after 1-4: about 175-185 s. Below about 2.5 min needs engine changes.
**Status:** not applied yet; the user chose to continue with Phase 4b first.

---

## Step 12: Phase 4b, the two-way bridge (QWebChannel)

**Asked:** create this log (done, Step 1-11 written up), then continue with Phase 4b.
**Built:** `bridge.py` (one `gem` object on the page's `QWebChannel`: only ids, names and seconds
cross it, never data), `app/web/src/bridge.ts` (page side; does nothing outside Qt, so the figure
page still works in a plain browser), a new `heroFollowed` figure event in `api.ts`, the scheme
handler serving Qt's own `qwebchannel.js` from Qt's resources (no copy), `select_fight` on the
Fights table and `select_hero` on the roster, which change the selection without announcing it so
there is no echo loop.
**Directions now live:** Fights table row to figure (opens that fight); figure fight pick to table
row; roster click to figure (follows that hero); figure hero follow to roster highlight.
A command sent before the page connects (a click while the figure loads) is kept, latest of each
kind, and sent when the page calls `ready()`. Replaced the earlier `runJavaScript` calls.
**Verified:** 62 fast app tests (4 new bridge unit tests, 7 new tests that drive the real web view:
connect, both fight directions with an "no echo" check, the pre-load pick, both hero directions);
8 plugin tests; ruff, mypy, `tsc` clean. **Mutation check:** with the page-to-Python events
disabled, exactly the two figure-to-app tests failed, then restored. **Real replay:** table row 18
opened fight 18 in the figure; clicking Chaos Knight in the roster made the figure follow Chaos
Knight; following Juggernaut in the figure highlighted Juggernaut in the roster (hero names match
between roster and figure).
**Found by looking:** the selected table row drew a blue bar on every cell; removed it and
strengthened the selection tint.
**Not done:** `timeChanged` is not sent to Python (it fires every frame during playback; add a
throttled version if a native clock is wanted); seek/play/pause commands exist on the bridge and the
page but have no native controls yet.
**One slip in the process:** a helper script replaced a real line in `dashboard.py` with a
placeholder; caught on the next read and restored before any test ran.

---

## Step 13: Native playback controls (seek, play, pause, steps, speed)

**Asked:** build the native controls for the seek/play/pause commands the bridge already had, then
ask before continuing with Phase 5.
**Built:** `transport.py` (`TransportBar`: Play/Pause, -10 s and +10 s, a seek slider in tenths of a
second, the clock and `seconds / length`, speed chips 0.25x-4x; shortcuts Space and Ctrl+Left/Right
registered window-wide), placed above the figure in the dashboard. The figure API gained
`getState()` and `setSpeed()`; `bridge.ts` reports the player's state to Python when it changes
(polled every 200 ms, sent only on change); `bridge.py` gained `speedRequested`, `request_seek`,
`request_playing`, `request_speed` and the `playback_changed` signal; new QSS for the controls.
**Behaviour worth knowing:** the controls mirror the page (press Play in the figure and the native
button changes) and send commands back without echo (following the page never sends a seek). A
seek pauses the figure's player, so a step taken while playing asks it to play again. The slider is
not pulled away from the user's hand while it is held. Controls are disabled when no fight is open.
**Correction found by testing:** I had assumed a fight with fewer than 3 deaths (no map playback)
has no player to control. It does: its feed and damage timeline still play, so the controls stay
enabled with that fight's own length. The disabled tooltip I had written ("3 or more deaths") was
wrong and was fixed.
**Verified:** 80 fast app tests pass (9 widget tests, 2 bridge, 8 real-player integration tests:
enable on a fight, native and page play/pause both ways, slider and step seeking including clamp at
the start, speed chips, the Space action, a breakdown-only fight, no controls with no fight); ruff,
mypy and `tsc` clean. **Mutation check:** with `request_speed` disabled, exactly the speed test
failed; restored. **Real replay:** table pick of fight 18, 4x speed, slider to 18 s, Play (about
10 s of fight in 2.5 s at 4x), then a -10 s step while playing kept playing. Viewed on screen.
**Not done:** a native control for the figure's other layers/filters; the match-clock text in the
bar comes from the page (it is the figure's clock, not computed in Python).

---

## Step 14: Phase 5, every figure in its own tab

**Asked (answers):** each figure in its own tab; do Phase 5 before any speed-up, and ask before doing
the speed-up. Also asked how to run the app while phases are built (answered: from `app/`,
`.\.venv\Scripts\python -m gemstudio [replay.dem]`; rebuild the figures with `npm run build` in
`app/web` after changing them).
**Built:**
- `app/web`: five new pages (objectives, lanes, runes, lead, wards), each the site's own markup and
  `mount*Figure` on run-time data, with a shared `figure-page.ts`; all six pages are Vite inputs.
- `figures.py`: `FigurePage` = one web view + its own bridge + a JavaScript-error log; the tab list
  (`FIGURE_PAGES`) and the placeholder sections. Pages are created the first time their tab is shown and
  reload when a different replay is opened (a token per replay).
- Window: tabs are Fight Replay & Dashboard, Objectives, Lanes, Runes, Gold & XP Lead, Wards, then the
  design's Scoreboard & Players and Batch & Parquet Export as disabled placeholders. The roster rail,
  facts strip and telemetry drawer stay on every tab; the playback bar shows on the Fights tab only.
- Links in the objectives and lead figures that point at a fight (`...#fight-N`) would have navigated
  the web view away. The page now intercepts them and the app switches to the Fights tab and opens that fight
  (new `openFight` bridge slot).
**Edge case found in the site's code (not edited):** with no minute-by-minute data, the site's lead
figure builds an invalid SVG path (`"M0,100.0 L L1000,100.0 Z"`) and throws. The lead page now checks
first and says "No minute-by-minute gold or XP data was recorded in this replay." The other four figures
handled empty data without errors.
**Verified:** 90 fast app tests pass (new: tab list and placeholders, each figure renders on its own tab
with no JavaScript errors, lazy creation, reload for a new replay, fight link opens the Fights tab and the
figure does not navigate, all five figures on a replay with no events); ruff, mypy, `tsc` clean.
**Mutation check:** with the Python `openFight` slot disabled, the link test failed; restored.
**Real replay:** all six tabs loaded with zero JavaScript errors; viewed the objectives and lead tabs.
**Mistakes made while testing (fixed):** a test clicked an objective twice, which un-picks it; and
`runJavaScript` does not reliably return a raw JavaScript array (use JSON text). Both were test bugs, not
app bugs; the isolated debug runs showed the app was right.
**Unexplained, to watch:** one full-suite run did not finish within 10 minutes (two Python processes
stayed alive, no web-engine process); the same suite then ran to completion in 101 s. Possibly a hang at
exit with several web views. If it recurs, look at page and profile teardown order in the test fixture.
**Not done:** the Scoreboard & Players and Batch & Parquet Export tabs; lanes/runes/wards were verified by
tests but only objectives and lead were looked at on screen.

---

## Step 15: Phase 6, the Windows installer

**Asked:** start Phase 6 (the installer).
**Built (all under `app/`):**
- `packaging/gemstudio.spec` + `entry.py`: a PyInstaller one-folder, windowed build. It bundles the
  compiled figures, hero icons, the site's exporter script, the cookbook recipes, the 7.41 map, gem's data
  files and licence notices, keeping the repository layout the exporter expects. `pyarrow` is left out
  (only Parquet export uses it).
- `packaging/gemstudio.iss`: an Inno Setup installer: per-user (no administrator rights), Start-menu
  shortcut, optional desktop icon, lists Gem Studio under "Open with" for `.dem` without taking the default.
  It never touches the user's saved replays. The AppId is fixed (a test guards it: changing it strands upgrades).
- `scripts/build_app.ps1`: one command for icons, figures, notices, bundle, a **self-test of the frozen app**
  (no Python on PATH, empty data folder), optional signing, then the installer. It stops at the first failure.
- `gemstudio/selftest.py` + `--self-test`/`--version`/`--report` on the exe: reads a real replay with the
  real worker processes, checks the figure data, the dashboard and every figure tab for JavaScript errors.
- `packaging/collect_licenses.py` (notices: MIT engine, Qt LGPL, Chromium, SIL fonts, Valve's artwork),
  `make_icon.py` (a placeholder icon), `requirements-build.txt`, `scripts/sign_files.ps1` (optional signing),
  and a GitHub workflow `.github/workflows/gem-studio-installer.yml` (a new file; tag or manual only).
  **The workflow has not been run.**
- `GEMSTUDIO_DATA_DIR` overrides the data folder; the cache key now includes the app version.

**Measured:** bundle 583 MB unpacked (PySide6 with QtWebEngine is 448 MB of it), installer 167 MB, whole build
about 7.5 min (PyInstaller 160 s, installer compression about 4 min). Frozen app on the full 36-minute replay,
cold: 38 fights read and all six figure tabs loaded in 166 s (faster than the 3.5 min from source).

**Bugs found only by testing the frozen app (fixed):**
1. My first "frozen self-test passed" was hollow: it reused my development cache, so the parse and export never
   ran in the bundle. A cold data folder (`GEMSTUDIO_DATA_DIR`) is now part of the test.
2. Cold, the frozen exporter crashed on `import pandas`. PyInstaller's PySide6 hook loads Qt in every process,
   workers included, and Qt replaces `builtins.__import__`, which breaks pandas' `dateutil`/`six` import
   (`'_SixMetaPathImporter' object has no attribute '_path'`). Reproduced from source with one line
   (`import PySide6.QtCore; import pandas`). Fix: the worker restores Python's import function on start.
   Regression test with a control that reproduces the bug.
3. The self-test hung on a modal error dialog nobody could close; windows now record errors instead when
   `interactive` is off.
4. My self-test probe read `document.body` before the page had loaded and was reported as a page error
   (a test bug).

**Install/uninstall:** a first cycle was fully clean (installed 2404 files, shortcut and `.dem` "Open with"
registered, the installed copy passed 16/16 with Python stripped from PATH, uninstall removed files,
shortcut and registry, saved replays untouched).

**Not solved, and important: Smart App Control.** This machine has Windows 11 Smart App Control ON
(`VerifiedAndReputablePolicyState` = 1). Windows' Code Integrity log (events 3077/3033, policy
`{0283ac0f-...}`) shows it blocking *unsigned* files from the build: numpy's `random\_generator.pyd` (twice, once
in the build folder and once in the installed copy) and Inno Setup's uninstaller helper `_unins.tmp`. The blocks
are intermittent (the same bundle then passed three cold reruns), which fits reputation-based evaluation per
file. Effects seen: one build self-test failed, one installed self-test failed, and one uninstall failed
(I cleaned my own test install by hand: shortcut, `.dem` registry values and the uninstall entry; verified).
**Smart App Control has no "run anyway" choice for a user; only a trusted signature (or good reputation)
avoids it.** So an unsigned installer is not dependable for people who have it on. The build now supports
signing (`-PfxPath`; the mechanics were tested with a throwaway self-signed certificate, which Windows does
not trust, and removed), says plainly when a failure looks like this, and the docs explain it. I did not
change any Windows setting.
**Decision needed from the user:** how to get a trusted code-signing identity (Azure Trusted Signing, an
OV/EV certificate, or the Microsoft Store), before sharing the exe with others.
**Also open:** a true clean-machine test (this is Windows 11 Home: no Windows Sandbox; I approximated with a
stripped environment and a cold data folder); bundled fonts (Roboto Flex, JetBrains Mono); the engine version
string is `0.0.0+local` for a fork build; a legal review of `LICENSES.txt`; the GitHub workflow's first run;
whether to ship the Dota icons at all.
**Tool installed on this machine for the build:** Inno Setup 6.7.3 for the current user (winget, no admin).
PyInstaller was added to `app/.venv`.

---

## Step 16: Publishing: local build, GitHub build, and the README link

**Asked:** skip the certificate for now; how to build the exe locally, how GitHub builds it, and a link on the
project README so people can try it.
**Done:**
- Root `README.md`: a short "Try it: Gem Studio" block right after the first divider, with a link to
  `releases/latest`, a pointer to `app/README.md`, and an honest note that the installer is **not code-signed**
  (SmartScreen warning; Smart App Control may block it) and that the first open of a replay takes a few minutes.
  **This edits an upstream file** (the README), against the usual rule: it is 7 lines in one place, so a future
  upstream merge conflict there is small and obvious (keep both).
- The GitHub workflow's build step now sets `QT_QPA_PLATFORM=offscreen` and
  `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu --no-sandbox`, because a hosted runner may have no display.
**Checked locally:** the workflow YAML parses; the packaged app's self-test passes in offscreen mode (16/16 on two
reruns). A third run failed with the same Smart App Control block on numpy's `_generator.pyd` (it is now blocked
in roughly 1 run in 3 on this machine). GitHub's hosted runners do not have Smart App Control.
**Not done / not verified:** the workflow has never run on GitHub; nothing has been committed or pushed (the user
has not asked); the release link shows "no releases" until a `studio-v*` tag is pushed and the workflow succeeds.
**Decision flagged:** the public installer would contain Valve's hero/item icons and map image (fetched at build
time by the repo's scripts). `LICENSES.txt` says they are Valve's; whether to ship them publicly is the user's call.

---

## Step 17: Fights tab layout, the all-fights map button, and why the replay is cropped

**Asked (on the conversation branch "UI-change"):** in "Fight Replay & Dashboard", put the replay on top with the
fight log on its right (60/40, the 40 for the log); add a button to show the all-fights map; and explore why the
whole match is not one replay with every hero's movement, and why the map is cropped.
**Built (`app/web/src/fights-layout.css`, `fights.ts`; no site file touched):**
- Top: the open fight's replay (map, playback controls, damage strip) at 60% and the fight log (hero health
  boxes, filters, the scrolling feed) at 40%. The log is exactly as tall as the replay and scrolls inside it.
- Below: the size filters (with the button at their right end), the timeline and the fight list.
- The map of all fights is hidden until the **All fights map** button is pressed (it then reads "Hide the all-fights
  map"). Picking a fight on that map still opens its replay. The map's legend only shows with the map.
- Under 700 px of figure width it falls back to one column (the app's minimum window gives about 820 px, so the
  60/40 split holds across the supported sizes).
**Verified:** measured on the real replay: replay column 664 px, log 443 px (60.0/40.0), both 953 px tall, the
replay above the list, the all-fights map hidden then shown by the button. 3 new tests (60/40 and heights, the
button toggle, picking a fight on the all-fights map). **Mutation check:** changing the split to 50/50 failed the
60/40 test (`replay is 50.0% of the row, not 60%`); restored. 106 app tests, 8 plugin tests, ruff, mypy, tsc clean.

**Findings: why the map looks cropped**
- *The overview (all-fights) map is not hiding anything.* The source image is 8878 x 8356 px; the app uses its
  centred square, and the calibration (`MAP_XMIN..MAP_YMAX`, an 18322-unit square) is defined for exactly that
  square. I projected all 360,747 hero readings of the whole game: every one lies inside it (x 36-948, y 63-986
  of 0-1000), zero outside. The dark corners are void areas of the Dota map.
- *The replay map is cropped on purpose.* Each playback frames a square around the fight: the hero positions
  within 2600 world units (`FIGHT_RADIUS`) of the fight's centre, plus padding (`fight_box`, `_crop` in
  `scripts/export_site_home_data.py`). On this replay the crops are 28-36% of the map's width, so a hero
  elsewhere is off-screen (heroes far from the fight are in the data but outside the view box).

**Findings: why there is no whole-match replay of all heroes**
- The data exists: the app's cache holds every hero's position on every packet (about 15 per second) for the whole
  game, 360,747 readings, 26.6 MB (`states.json`).
- The export keeps only the playback windows (`_within`), and only fights with 3 or more deaths get a playback
  (`PLAYBACK_MIN_DEATHS = 3`): 9 of 38 fights here. The other 29 have a breakdown (feed and timeline) but no map.
- The site's player (`createPlayer`) is built around one fight: its casts, damage, deaths and per-fight crop. It
  has no whole-match mode.
**Options offered (not built):** (1) a "Full map" toggle for fight replays (feasible without site edits by
overriding each fight's box and image in the page's data); (2) a new "Match replay" tab: all ten heroes on the
whole map for the whole game, with play/pause/speed, a scrubber and fight markers, from the cached positions
(medium effort: new page and export); (3) playbacks for all 38 fights (small change, bigger export).

---

## Step 18: Why some fights have no replay, and Previous / Next fight arrows

**Asked (two things):** (1) explore why some fights get no replay in the app; (2) the timeline bar under the replay:
when fights are highlighted by drag and drop the replay window disappears or appears; highlight the fights or add
next/previous arrows so a click moves forward or back through the fight replays.

**(1) Why some fights have no map replay (nothing changed yet).** Verified on the real replay: a fight gets a map
replay only if it has 3 or more deaths (`PLAYBACK_MIN_DEATHS = 3` in the site's export script). 1 death: 0 of 21
had one; 2 deaths: 0 of 8; 3 deaths: 8 of 8; 4 deaths: 1 of 1. No exceptions. Fights below the threshold get the
breakdown (feed and timeline) without the map. The likely reason is file size (a replay file averages 115 KB, a
breakdown 5 KB); that is an inference. Many fights are small because gem groups deaths by time (15 s) and place
(3000 world units, about 164 of 1000 map units): e.g. #24 and #25 are 2 s apart but half a map apart (3 deaths
combined, each below the threshold). Thresholds: 2+ deaths would give 17 of 38 replays, 1+ would give all 38; the
whole-game positions are already cached, so the extra cost is file size and export time (not measured). Options
offered: replay for every fight, or a setting. Awaiting the user's choice.

**(2) Built (`app/web/src/fight-nav.ts`, `fights-layout.css`, `fights.ts`; no site file touched).**
Cause of the vanishing replay: the site treats a drag on the timeline as a *filter* (`fightsIn` keeps only fights in
the stretch) and `pickShown` then swaps the open fight for the biggest one in the stretch, or closes it when there
is none. Now:
- A **Previous fight / Next fight** bar above the replay: "Fight 18 · 14:29 (18 of 38)", and a tag saying "Map
  replay" or "Breakdown only: no map replay". The arrows step through the fights the list currently shows (the
  size filter 2+/3+/5+ still applies), are disabled at the ends, and follow changes the figure makes itself.
- Dragging on the timeline does nothing (the site's drag picker is blocked in the capture phase). A *click* on a
  fight's bar opens that fight (nearest bar within 2.5% of the timeline; when bars overlap, the one whose middle is
  closest). The hint now reads "Click a fight to open its replay"; the range pill is hidden.
- Everything works by clicking the figure's own list buttons, as a user would.
**A bug of mine found by testing:** the first version treated the end of a drag as a click and opened the nearest
fight (the debug run showed the open fight jump 19 to 23 while the list stayed at 36). A press and release now
count as a click only if they are within 4 px.
**Verified:** 5 new tests drive the real page (arrows and their end stops, the map-replay tag, a drag changing nothing
including a drag over an empty stretch, a click opening a fight, arrows following the size filter). **Mutation
check:** letting the site's drag handler through again failed the drag test with the reported symptom (open fight
19 became 17); restored. Real replay: Next 18 to 19, a long drag left fight 19 open with all 38 fights listed and
the replay showing, Previous back to 18. 111 app tests, ruff, mypy, tsc clean.
**Not rebuilt:** the exe and installer in `app/build` predate this change; rebuild with `build_app.ps1`.

---

## Step 19: Full rebuild and Rebuild-Readme.txt

**Asked:** do a full rebuild and write all the commands into `Rebuild-Readme.txt` at the project root.
**Done:** ran `app/scripts/build_app.ps1` end to end (about 9 minutes): figures, PyInstaller bundle (583 MB), the
frozen app self-test (16/16, no Python on PATH, cold data folder), and the Inno Setup installer (167 MB). Confirmed
the new Fights layout, the all-fights map button, the Previous/Next arrows and the click-to-open timeline are in
the bundle. `Rebuild-Readme.txt` lists: the full rebuild and its variants, rebuilding only the figures, running from
source, running and self-testing the exe, testing the installer silently, tests and checks, one-time setup on a new
machine, the version number, signing, building and publishing on GitHub, and troubleshooting (including Smart App
Control blocks).
**Still true:** the build is unsigned; nothing is committed or pushed.

---

## Open items carried forward
- Speed-ups 1-4 above (app-side, optional).
- The Scoreboard & Players and Batch & Parquet Export tabs (design sections, not figures).
- Code signing (see Step 15: Smart App Control), a true clean-machine test, the GitHub workflow's first run.
- Bundle Roboto Flex and JetBrains Mono (open licence); decide whether to ship icons.
- Rotate the Stitch API key that was pasted into the chat.
