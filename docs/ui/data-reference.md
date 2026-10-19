# gem data reference for UI design

Source: gem-dota 0.13.0 (`src/gem/cli.py`, `results/dataframes.py`, `results/models.py`, `replays/fetch.py`).
Purpose: input for designing a desktop UI (e.g. in Claude Design).

## 1. Data sources

| Source | How it gets in | Notes |
|---|---|---|
| Local `.dem` file | File picker / drag-and-drop | Primary input. Parsing is offline, no API key. |
| Match ID (download) | `gem.fetch_replay(match_id, out_dir)` | OpenDota API (`api.opendota.com/api/matches/{id}`) for the replay URL, then Valve CDN. `.dem.bz2` or zstd is decompressed automatically; skipped if the `.dem` exists. Only network feature. Valve expires replays; CDN download is plain HTTP. |
| Folder of `.dem` files | Directory picker | Batch parsing, optionally recursive. |
| Saved gem JSON | `gem.load_json(path)` | Reload without re-parsing. The `analysis` section is not restored; call `gem.analyze(match)`. |
| Saved Parquet folder | `gem.read_parquet_table(...)` | Reads one table across many replays. |
| OpenDota match JSON | `gem.replays.fetch.fetch_opendota_match(id)` | For comparing against OpenDota. Likely not v1. |

## 2. CLI options the UI must expose

### `python -m gem parse <file.dem>`

| Option | Values | UI control |
|---|---|---|
| `--format` | `summary` (default), `json`, `parquet` | Output type |
| `--output` | file (json) / directory (parquet) | Save picker. Required for parquet; omitted json prints to stdout. |
| `--include` | `analysis`, `opendota`, `gold_ledger` (repeatable) | Checkboxes (parquet) |
| `--analysis` | flag; only with `--format json` | Checkbox |
| `--progress`, `--timings`, `--quiet/-q`, `--no-banner` | flags | Terminal-only; UI replaces with progress bar / timing readout |

### `python -m gem batch <dir|files...>`

| Option | Notes |
|---|---|
| `--output` | Required. One subfolder of parquet per replay. |
| `--workers` | Parallel processes; default `os.cpu_count()`. Slider. |
| `--recursive` | Scan subfolders. |
| `--include` | Same three groups. |
| Result | Per replay `ok` / `error`. Show failed-replays table (path, error). |

The CLI has no fetch command; download-by-match-ID exists only in the Python API.

## 3. Data contents

### Summary view (CLI)
Hero kills, towers, barracks, Roshan kills, Aegis events, wards, buybacks, runes, chat count, duration; per player: team, hero, LH, gold, purchases, runes, buybacks.

### `ParsedMatch` (match level)
- Header: `match_id`, `game_mode`, `leagueid`, team ids/names/tags, `radiant_win`, `radiant_score`, `dire_score`, `duration`, `first_blood_time`, `pre_game_duration`.
- Events: `draft`, `fights`, `opendota_teamfights`, `wards`, `runes`, `towers`, `barracks`, `roshans`, `aegis_events`, `tormentors`, `shrines`, `courier_deaths`, `courier_snapshots`, `chat`, `smoke_events`, `neutral_item_finds`, `banner_plants`.
- Curves: `radiant_gold_adv`, `radiant_xp_adv` (per minute).
- Raw logs: `combat_log`, `hero_visibility_events`, `entity_visibility_events`, `vision_modifiers`.
- Health: `parse_error`, `truncated_at_tick`, `game_clock`, `post_game_tick`.

### `ParsedPlayer` (~130 fields)
- Identity: `hero_name`, `hero_id`, `player_name`, `steam_id`, `account_id`, `team`, `is_radiant`, `win`.
- Stats: kills/deaths/assists, `kda`, `last_hits`, `denies`, `net_worth`, `gold_per_min`, `xp_per_min`, `hero_damage`, `tower_damage`, `hero_healing`, `stuns_dealt`, `teamfight_participation`, lane fields, wards placed, camps stacked, etc.
- Timeseries (per second `*_t` and per minute `*_t_min`): gold, XP, net worth, LH, denies, `hp_t`, `mana_t`.
- Positions: `position_log`, `lane_pos`.
- Dicts: `damage`, `damage_taken`, `damage_inflictor`, `damage_targets`, `ability_uses`, `item_uses`, `purchase`, `purchase_time`, `multi_kills`, `kill_streaks`, `killed`, `killed_by`, `gold_reasons`, `xp_reasons`.
- Logs: `kills_log`, `purchase_log`, `runes_log`, `buyback_log`, `buybacks`, `obs_log`, `sen_log`.
- Other: `final_items`, `gold_ledger`, `aghanims_scepter`, `aghanims_shard`, `moonshard`.

### Export tables
Core (always, 26): `match`, `player_summary`, `player_timeseries`, `players_minute`, `player_breakdowns`, `positions`, `radiant_advantage`, `combat_log`, `wards`, `objectives`, `chat`, `draft`, `fights`, `fight_players`, `smoke_events`, `smoke_members`, `courier_snapshots`, `neutral_item_finds`, `hero_visibility_events`, `entity_visibility`, `vision_modifiers`, `vision_modifier_pairing_issues`, `player_kills_log`, `player_purchase_log`, `player_runes_log`, `player_buyback_log`.

Optional groups (`--include`):
- `analysis`: `fight_positioning`, `roshan_conversions`, `roshan_conversion_fights`, `farming_routes`, `farming_route_segments`, `farming_route_points`
- `opendota`: `opendota_objectives`, `opendota_teamfights`
- `gold_ledger`: `player_gold_ledger`, `player_gold_ledger_minutes`

Every table starts with `match_id`; fixed nullable dtypes (`Int64`, `Float64`, `boolean`, `string`); list fields are `;`-joined.

### Bundled reference data (`src/gem/data/`)
`heroes.json`, `items.json`, `abilities.json`, `leagues.json`, `xp_level.json`, `camp_zones.json`, `map_constants.json`, `ancients.json`, `permanent_buffs.json`. Hero/item icons are NOT bundled (fetched by `scripts/fetch_hero_icons.py`, `fetch_item_icons.py`). Map images: `assets/maps/`.

## 4. Design constraints
- `gem.parse` has no progress callback: single file = indeterminate spinner; batch has per-file progress.
- Ticks are not seconds. Use `match.game_clock` (`game_seconds_at`, `format_tick`); never `tick // 30`. (The CLI summary does this; do not copy it.)
- Team `2` = Radiant, otherwise Dire.
- gem presents facts, not verdicts: no scores/tags/"good play" labels.
- `analysis` outputs are experimental; label them so.
- Warn when `parse_error` or `truncated_at_tick` is set.

## 5. Suggested screens
1. Open replay (drop `.dem` / match ID / folder)
2. Match overview (scoreboard, gold/XP advantage chart, event timeline)
3. Player detail (timeseries, items, abilities, damage breakdowns)
4. Events explorer (fights, wards, runes, objectives, draft, chat)
5. Export (format, include groups, folder) + batch queue (workers, failures)
6. Settings (default folders, workers, parsed-JSON cache)
