# Dashboard-Gem: design notes

Pulled from Stitch project `18090275263856862448`, screen `5bf31b1627014e79b377a8c940c2345c`
("Gem Workbench - Material 3 Telemetry"). Files here are reference only, not shipped:

- `dashboard.html`: Stitch's export (Tailwind + mock data). **Untrusted generated markup; read it, do not execute or ship it.**
- `dashboard.png`: a 421 px thumbnail (Stitch's API returned only this size).

## Two design systems in the project

| | Material Telemetry Dark (used by this screen) | Obsidian Ancient (the project's default theme) |
|---|---|---|
| Look | Material 3, blue accent `#8ab4f8`, 8 px rounded | Dota client: gold `#d1a054`, sharp 0 px corners, bevels |
| Fonts | Roboto Flex + JetBrains Mono | Cinzel + Inter + JetBrains Mono |
| Surfaces | `#131314` / `#1e1f20` / `#28292a` / `#333537` / `#3c4043` | `#0e1217` / `#13171d` / `#1a1e24` / `#282e38` |

**Open question for the user:** which one the app follows. This note assumes the Dashboard-Gem
screen's own system (Material Telemetry Dark) until told otherwise.

## Material Telemetry Dark tokens (from the screen)

- Text `#e8eaed`, secondary `#9aa0a6`, tertiary `#80868b`
- Primary `#8ab4f8` (hover `#a6c8ff`), on-primary `#131314`, secondary `#78d9ec`
- Borders `#3c4043` (subtle), `#5f6368` (strong)
- Faction/data: Radiant `#81c995`, Dire `#f28b82`, Pure/warning `#fdd663`, Magical `#c58af9`, Physical `#e8eaed`
- Radii 4 px (chips), 8 px (controls), 12 px (cards); spacing on a 4/8 px grid
- Type: Roboto Flex 12-14 px body, JetBrains Mono for numbers, times, ticks

## Layout

```
┌ top bar (48 px): gem / engine status · transport (-10s ⏮ ▶ ⏭ +10s, clock, tick, speed) · Open .dem · Fetch ID · settings
├ tab bar: Fight Replay & Dashboard | Scoreboard & Players | Vision & Wards | Events & Objectives | Batch & Parquet Export
├ left rail (256 px): Radiant roster + net-worth lead, Dire roster, scrub-rate chips
├ main: fight chips · layer toggles · map/player figure · roster telemetry · sequential combat feed · fight summary
└ bottom: "Analytical Telemetry" drawer (toggle; expands to tabs: Gold & XP curve, Damage matrix, Farming routes, Net worth) + footer buttons
```

The bottom drawer is the **Analytical Telemetry toggle** the user asked for.

## Mapping to the hybrid app

| Design area | Built as |
|---|---|
| Top bar, tabs, left rail, footer | native Qt widgets (QSS from the tokens above) |
| Map + fight playback + combat feed | the site's fights figure in `QWebEngineView` (already built in `app/web`) |
| Roster telemetry, scoreboard | native widgets over `ParsedPlayer` / DataFrames |
| Analytical Telemetry drawer | collapsible bottom dock: native tables + pyqtgraph curves |
| Open .dem / Fetch ID | Phase 2 (file open) and the match-ID download job |
| Batch & Parquet Export tab | wraps `parse_many_to_parquet` (CLI `batch`) |

## Things in the mock that gem cannot or should not show

gem reports facts, not verdicts (CLAUDE.md). The mock contains content to leave out or reword:

- Interpretive labels: "CLIMAX", "Radiant Frontline: Low River Trench", "BLINK AGGRESS",
  "Fight Aggregate Outcome: Dire sustained more kills; Radiant secures River Control & Roshan lead".
  Facts available instead: kills per side, gold/XP change, what fell next (`FightEntry.next`).
- "PARQUET AGGREGATION: 10hz RESAMPLED", "Parser Engine Status: 100% INGESTED", "Parquet writer: ready":
  decorative; the engine has no such status or resampling.
- "Live" HP/mana for all ten heroes at every frame exists only for fights with a playback (3+ deaths).
- Ward counts, buybacks and max gold swing are derivable; "Max Gold Swing @ time" needs a defined calculation.
- Mock match data (TI 10 grand finals, names, numbers) is placeholder.
