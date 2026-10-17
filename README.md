# trckr

A minimal, event-driven time and count tracking engine designed for zero-friction logging.

## Core Concept

`trckr` eliminates the overhead of managing complex, stateful tracking records by reducing every user action down to an append-only stream of immutable, timestamped events.

- **Items**: User-defined templates (`timed` or `counted`) that represent what is being tracked.
- **Groups**: Mutual exclusion categories for `timed` items. Starting a timer in a group automatically stops any other running timer within that same group.
- **Events**: Append-only log entries containing an `item_id`, `timestamp`, and state metadata.
- **State Engine**: Current item states, active timers, and aggregate counts are calculated dynamically by reading the event stream on the backend.

## CLI Architecture & Logic Flow

The `trckr` CLI (`src/cli.py`) acts as the primary operational entry point and management interface. Built with Python's `argparse`, it maps subcommands to core engine triggers, state queries, and resource management tasks. Python 3.14 and [uv](https://docs.astral.sh/uv/) are the expected toolchain.

### Command Hierarchy

````text
trckr [--data-dir DIR]
├── item                    # Tracked Item Management
│   ├── add <label>         # Create item (--type, --group, --tags)
│   └── list                # List all items (--tag, --json)
├── group                   # Auto-Stop Group Management
│   ├── add <label>         # Create a mutually exclusive timer group
│   └── list                # List existing auto-stop groups
├── tag                     # UI Metadata Registry
│   ├── set <tag>           # Configure tag visual properties (--color, --icon)
│   └── list                # List active tags and registered styles
├── trigger (alias: t)     # Core Event Ingestion
│   └── <item_ref>          # Start/stop timer or increment count (--source)
└── log                     # Historical Event Audit Log
    └── [--item] [--tag]    # View immutable event log (--limit)

The CLI is a stdlib-only `argparse` program with no runtime dependencies. Python 3.14 and
[uv](https://docs.astral.sh/uv/) are the expected toolchain.

```bash
uv sync                 # creates .venv, installs pytest and the `trckr` script
uv run trckr --help
uv run python -m pytest # run the test suite
````

Data lives in four JSON files under `./data/` by default (gitignored). Override the location
with `--data-dir PATH` or the `TRCKR_DATA_DIR` environment variable.

```bash
trckr group add "Work"
trckr item add "Coding" --group Work --tag dev
trckr item add "Meeting" --group Work
trckr item add "Water" --type counted

trckr trigger Coding          # starts the Coding timer
trckr trigger Meeting         # auto-stops Coding, starts Meeting
trckr trigger Water           # counted item: count -> 1

trckr item list                  # running/stopped, elapsed, totals, counts, tag colors
trckr item list --json
trckr log --item Coding --limit 20
trckr tag set dev --color "#007AFF" --icon code
trckr tag list
```

Items and groups can be referenced by id (`itm_505c5a3a`) or by label (case-insensitive).
Without installing, `python -m src.cli ...` from the repo root works too.

---

## Data Architecture

### Schema Models

#### 1. Event (`schemas/event.json`)

An immutable point-in-time record generated manually (via tap/widget) or automatically (via group linkages or sensors).

```json
{
  "id": "evt_101",
  "item_id": "itm_102",
  "timestamp": "2026-10-03T14:15:30Z",
  "action": "start",
  "source": "widget"
}
```

#### 2. Group (`schemas/group.json`)

Defines a mutual exclusion category for timed items.

```json
{
  "id": "grp_101",
  "label": "Work Stuff",
  "created_at": "2026-10-03T09:00:00Z"
}
```

#### 3. Item (`schemas/item.json`)

Defines the template for a tracked item.

```json
{
  "id": "itm_102",
  "label": "Pipeline Project",
  "type": "timed",
  "group_id": "grp_101",
  "tags": ["work", "project"],
  "created_at": "2026-10-03T09:00:00Z"
}
```

#### 4. Tag (`schemas/tag.json`)

Optional visual metadata registry (stored in `data/tags.json`) used for UI badges, colors, and dashboard icons without affecting core event logic.

```json
{
  "id": "homework",
  "color": "#0A84FF",
  "icon": "book"
}
```

## Repository Structure
````text
trckr/
├── docs/ # Architecture decision records & design specs
├── schemas/ # JSON Schemas (group.json, item.json, event.json, tag.json)
├── src/
│ ├── main.py # argparse CLI (`trckr`); wires engine to storage
│ ├── core/ # State resolver, group auto-stop, & get_auto_color() utility
│ ├── storage/ # Local database & append-only log engine
│ └── integrations/ # (planned) Widget, sensor, and external trigger ingestion
└── tests/ # Core logic and CLI test suite

### State Resolution Rules

Counted Items: Aggregated using COUNT(events) over a specified timeframe.

Timed Items: An odd number of events indicates a running timer; an even number indicates a stopped timer.

Group Switching: Starting a timed item with a non-null group_id triggers an ingestion lookup to halt any active timer in the same group, emitting an auto-generated stop event with matching timestamp.
