## Why

About fifteen seconds after setup, TendrilGrow loads every storage-mode Lovelace dashboard and saves rewrites that retarget the old week-in-stage number entity. That edits dashboards the operator did not ask to change.

## What Changes

- Stop automatic `async_load` / `async_save` of Lovelace dashboards.
- When a storage dashboard still references a retired stage-clock entity id, raise a Home Assistant repair that names the old id and the replacement, and leave the dashboard file untouched until the operator edits it.
- Keep the entity-registry id migration that already renames TendrilGrow's own entities.

## Capabilities

### New Capabilities

- `lovelace-migration-repair`: Retired stage-clock entity references are reported as a repair. Dashboards are not rewritten by the integration.

### Modified Capabilities

## Impact

- `__init__.py` `_async_migrate_lovelace_stage_clock` and the delayed call site.
- `repairs.py` and strings for the repair issue.
- Tests that a setup does not call dashboard save, and that a known stale entity id produces a repair.
