# ADR 002: String Tags and Tag Registry for UI Aggregation

- **Status**: Accepted
- **Date**: 2026-10-16

## Context

Items needed a way to be categorized and compared in the UI (e.g., comparing star charts or homework timers across family members) without triggering auto-stop mutual exclusion rules.

## Decision

1. Retain `group_id` strictly for mutual-exclusion timer switching.
2. Add an optional `tags` array of strings to `Item`.
3. Introduce an optional `tag.json` metadata registry (`data/tags.json`) for custom UI attributes (colors, icons).
4. Fall back to deterministic auto-generated hex colors (`get_auto_color()`) when tag metadata is unconfigured.

## Consequences

- **Pros**: Clear separation between state behavior (`groups`) and visual reporting (`tags`). Zero friction during item creation.
- **Cons**: UI layer must map tags to items during aggregate queries.
