## Context

`_async_migrate_lovelace_stage_clock` runs about 15 seconds after the first entry loads. It walks every storage-mode Lovelace dashboard, rewrites retired week-in-stage entity ids, and calls `async_save`. That persists edits the operator did not make. Entity-registry migration for TendrilGrow's own entities is separate and should stay.

## Goals / Non-Goals

**Goals:**

- Setup never calls Lovelace `async_save`.
- A repair names the stale entity id and the replacement entity id when a storage dashboard still references the old week-in-stage number.

**Non-Goals:**

- Rewriting YAML-mode dashboards.
- Migrating unrelated cards.
- A one-click "fix my dashboard" action in the first version. The repair tells the operator what to change.

## Decisions

### Delete the delayed save

Remove the `async_call_later(..., _async_lovelace_stage_clock)` registration and the save path. Keep pure functions that compute old-id → new-id pairs; use them only to build the repair description.

### Repair, not a write

On setup, if the computed replacement map is non-empty, scan loaded storage dashboard config in memory. If a stale id is present, create a repair issue (one per dashboard url path, or one integration issue listing paths). Dismiss the issue when a later setup scan finds no stale ids. Never save.

Alternative considered: keep the rewrite behind a repair "fix" button. Rejected for this change — a button that writes all dashboards is the same risk, just deferred. The operator edits the card.

## Risks / Trade-offs

- [Operator misses the repair and the card stays empty] → The repair text includes both entity ids so the card can be updated in one edit.
- [Dashboard config is not loaded yet at setup] → Schedule a read-only scan later, still without `async_save`. If the dashboard cannot be loaded, skip it and do not raise.

## Migration Plan

Upgrading stops future writes. Dashboards already rewritten by older versions stay as saved. No data rollback.

## Open Questions

None.
