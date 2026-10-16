# Architecture Overview

## Design Philosophy

`trckr` is built on an append-only event-sourcing model. The system does not mutate records when a user triggers an action; instead, it appends a timestamped event log. All current item states, active timers, and item counts are derived dynamically by processing the event stream.

## Core Entities

- **Events**: Immutable point-in-time entries created by manual taps, widgets, auto-links, or sensors.
- **Groups**: Mutual-exclusion categories for timed tracking.
- **Items**: User-defined tracking definitions (`timed` or `counted`).
- **Tags**: User-defined categories for items.

## Ingestion Pipeline

1. **Trigger Origin**: External tap / widget / sensor posts `{ item_id, timestamp, source }`.
2. **Ingestion Router**: Resolves `item_id` to its parent `Item` and checks its `type` and `group_id`.
3. **Group Resolver**: If `type == "timed"` and `group_id != null`, checks for running timers in the same group and generates auto-stop event(s).
4. **Log Storage**: Appends generated event(s) to the event stream.
