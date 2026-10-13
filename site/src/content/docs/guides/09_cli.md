# CLI Reference

gem ships a command-line interface you can invoke with `python -m gem`.

It covers two workflows:

- `parse` - parse one replay and print a summary, JSON, or Parquet output.
- `batch` - parse many replays in parallel.

## Quick examples

```bash
# Print a match summary
python -m gem my_replay.dem

# Export one replay to JSON
python -m gem my_replay.dem --format json > match.json

# Export one replay to Parquet files
python -m gem parse my_replay.dem --format parquet --output ./out

# Parse a folder in parallel
python -m gem batch replays/ --format parquet --output ./out --workers 4

# Add the optional post-parse analysis tables
python -m gem batch replays/ --output ./out --include analysis
```

## `parse` - single replay

```bash
python -m gem [parse] <path> [options]
```

::: info
The `parse` keyword is optional. `python -m gem match.dem` is identical to
`python -m gem parse match.dem`.
:::

| Option | Values | Default | Description |
|---|---|---|---|
| `<path>` | path to `.dem` | - | Replay file to parse |
| `--format` | `summary`, `json`, `parquet` | `summary` | Output format |
| `--output` | file or directory | stdout / cwd | Output destination. Required for `parquet`; optional for `json` |
| `--include` | `analysis`, `opendota` (repeatable) | none | Add optional Parquet table groups |
| `--analysis` | flag | off | With `--format json`, embed `gem.analyze()` results under an `analysis` key |
| `--progress` | flag | off | Show a live phase-by-phase progress bar |
| `--timings` | flag | off | Print a timing breakdown after parsing |
| `--quiet`, `-q` | flag | off | Suppress banner and non-essential output |
| `--no-banner` | flag | off | Hide the ASCII art banner but keep other output |

### Summary output

The default format prints a Rich table with per-player KDA, gold, net worth, last hits,
denies, and hero kills.

```bash
python -m gem my_replay.dem
python -m gem my_replay.dem --no-banner
python -m gem my_replay.dem --quiet
```

### JSON output

With `--format json`, the full `ParsedMatch` structure is serialized to JSON. Omit
`--output` to print JSON to stdout:

```bash
python -m gem my_replay.dem --format json
python -m gem parse my_replay.dem --format json --output match.json
```

Timings go to stderr when JSON is written to stdout, so piping works cleanly:

```bash
python -m gem my_replay.dem --format json --timings > match.json
```

### Parquet output

`--format parquet` writes one `.parquet` file per DataFrame table into `--output`:

```bash
python -m gem parse my_replay.dem --format parquet --output ./out

# Example files:
# out/player_summary.parquet
# out/player_timeseries.parquet
# out/combat_log.parquet
# out/fights.parquet
```

Every table starts with a `match_id` column. Add `--include analysis` for the
farming, Roshan and fight-positioning tables, or
`--include opendota` for the OpenDota-shaped objective and teamfight views. See
[Time-Series & DataFrames](05_timeseries.md) for the table list.

::: info Parquet dependency
Requires `pyarrow` or `fastparquet`.
:::

## `batch` - parallel multi-replay processing

```bash
python -m gem batch <source> [options]
```

`<source>` is either a directory path or one or more explicit `.dem` file paths.

| Option | Values | Default | Description |
|---|---|---|---|
| `<source>` | directory or file list | - | Replay(s) to parse |
| `--format` | `parquet` | `parquet` | Output format |
| `--output` | directory | - | Required root output directory |
| `--workers` | integer | `os.cpu_count()` | Number of parallel worker processes |
| `--recursive` | flag | off | Scan source directories recursively |
| `--include` | `analysis`, `opendota` (repeatable) | none | Add optional Parquet table groups |
| `--progress` | flag | off | Show a Rich progress bar |
| `--timings` | flag | off | Print timing breakdown after all replays |
| `--quiet`, `-q` | flag | off | Suppress all non-essential output |

### One Parquet directory per replay

```bash
python -m gem batch replays/ --format parquet --output ./out

# Output layout:
# out/
#   match_6789/
#     player_summary.parquet
#     combat_log.parquet
#     ...
#   match_6790/
#     ...
```

Parquet batch export writes completed replays serially in the parent process.
At most one replay per worker is outstanding, including completed matches waiting
for export. Slow writing applies backpressure instead of accumulating the batch.
Memory still includes worker processes, in-flight matches, IPC buffers, and one
match's complete DataFrame collection. Input and returned path metadata grow with
batch size; lowering `--workers` reduces the in-flight match limit.

For the Python API, `parse_many_to_parquet(..., timeout=seconds)` uses one
cooperative batch deadline after path collection, including parsing and writing.
Running parses and synchronous writes are not forcibly interrupted, so shutdown
can exceed the deadline. Parse failures are skipped; executor failures, export
errors, and timeouts propagate. Files already written, including partial exports,
remain on disk after failure. Duplicate replay stems retain the existing serial
overwrite behavior.

### Loading one table across replays

Load a single table from every replay directory with `gem.read_parquet_table()`. It
adds a `replay` column holding the per-replay directory name:

```python
import gem

combat = gem.read_parquet_table("./out", "combat_log")
summaries = gem.read_parquet_table("./out", "player_summary")
```

::: info Removed in 0.10.0
`batch --format dataframe` has been removed. It held every parsed match and every
table in memory before writing. Use the default Parquet layout plus
`gem.read_parquet_table()` instead.
:::

::: warning Exit codes
The `batch` command exits with code `0` even when some replays fail. It prints a summary
table of failed replays to stderr, so check the output before treating the batch as
complete.
:::

## `reports` (removed)

`python -m gem reports` was removed in gem 0.14 with the HTML report, and now exits
with a message pointing to the [Recipes](../cookbook/questions.md). See
[Match Reports](../reports/index.md) for where each report view went.

## Python API equivalents

```python
import gem

match = gem.parse("my_replay.dem")

json_str = gem.parse_to_json("my_replay.dem", indent=2)

gem.parse_to_parquet("my_replay.dem", output_dir="./out")

results = gem.parse_many("replays/", workers=4)

gem.parse_many_to_parquet("replays/", output_dir="./out", workers=4)
combat = gem.read_parquet_table("./out", "combat_log")
```

See the [API Reference](../reference/index.md) for full parameter documentation.
