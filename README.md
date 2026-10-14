# trckr

A minimal, event-driven time and count tracking engine designed for zero-friction logging.

## Core Concept

`trckr` eliminates the overhead of managing complex, stateful tracking records by reducing every user action down to an append-only stream of immutable, timestamped events.

- **Items**: User-defined templates (`timed` or `counted`) that represent what is being tracked.
- **Groups**: Mutual exclusion categories for `timed` items. Starting a timer in a group automatically stops any other running timer within that same group.
- **Events**: Append-only log entries containing an `item_id`, `timestamp`, and state metadata.
- **State Engine**: Current item states, active timers, and aggregate counts are calculated dynamically by reading the event stream on the backend.

---

## Data Architecture

### Schema Models

#### 1. Group (`schemas/group.json`)

Defines a mutual exclusion category for timed items.

```json
{
  "id": "grp_101",
  "label": "Work Stuff",
  "created_at": "2026-10-03T09:00:00Z"
}
```

#### 2. Item (`schemas/item.json`)

Defines the template for a tracked item.

```json
{
  "id": "itm_102",
  "label": "Pipeline Project",
  "type": "timed",
  "group_id": "grp_101",
  "created_at": "2026-10-03T09:00:00Z"
}
```

#### 3. Event (`schemas/event.json`)

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

## Repository Structure

trckr/
├── docs/ # Architecture decision records & design specs
├── schemas/ # JSON Schema definitions (group.json, item.json, event.json)
├── src/
│ ├── core/ # Event stream state resolver & auto-stop logic
│ ├── storage/ # Local database & append-only log engine
│ └── integrations/ # Widget, sensor, and external trigger ingestion
└── tests/ # Core logic test suite

### State Resolution Rules

Counted Items: Aggregated using COUNT(events) over a specified timeframe.

Timed Items: An odd number of events indicates a running timer; an even number indicates a stopped timer.

Group Switching: Starting a timed item with a non-null group_id triggers an ingestion lookup to halt any active timer in the same group, emitting an auto-generated stop event with matching timestamp.
