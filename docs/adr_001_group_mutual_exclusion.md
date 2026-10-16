# ADR 001: Group-Based Mutual Exclusion vs. Direct Item Linkages

* **Status**: Accepted
* **Date**: 2026-10-14

## Context
Initial designs stored an array of `auto_stop_linked_ids` inside each `Item` payload. As the number of items grew, manually configuring links between every combination of items created high setup friction for users.

## Decision
Replace direct item linkages with an explicit `Group` entity. Items belong to a single `group_id`. Starting a timed item automatically halts any other running timer inside the same group.

## Consequences
- **Pros**: Reduced setup effort, cleaner relational schema, automatic inclusion of newly added items into existing groups.
- **Cons**: An item can only belong to one mutual-exclusion group at a time.