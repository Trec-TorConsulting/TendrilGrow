# Proposal: add-grow-cultivation-context

## Why

Telemetry and a camera image are not enough for accurate agronomy advice — the
model also needs operator context: growth stage, strain, week in stage, reservoir
volume, plant/site count, target pH/EC, feed cadence, light hours, and the
nutrient line in use. Exposing these as editable Home Assistant helper entities
lets the grower keep context current and feeds it into AI health checks. This
capability is **already shipped**; this change documents it retroactively.

## What Changes

- Add per-grow-space **cultivation-context helper entities** that the operator
  edits directly in Home Assistant and that persist across restarts:
  - A **growth-stage select** (`select.py`) with stages seedling, vegetative,
    early_flower, mid_flower, late_flower, flush.
  - **Numeric context** (`number.py`): week in stage, reservoir volume (gal), site
    count, target pH, target EC, feed interval (days), lights-on hours, runoff
    target (%).
  - **Text context** (`text.py`): strain/genetics, nutrient line, base nutrients,
    additives.
- Add **per-stage target ranges** (`STAGE_TARGETS`) and a **context label map**
  (`GROW_CONTEXT_LABELS`) so AI health checks read these entities (by config-entry
  unique-id suffix) and calibrate scoring/advice to the current stage.
- Group all context entities under the grow space's Home Assistant device.

## Capabilities

### New Capabilities
- `grow-cultivation-context`: Editable, restore-on-restart cultivation-context
  helper entities per grow space (stage select, numeric context, text context),
  with per-stage target ranges and a label map consumed by AI health checks.

### Modified Capabilities
<!-- None — additive helper entities; AI health consumption is covered by ai-health-monitoring. -->

## Impact

- **New code**: `custom_components/tendrilgrow/select.py`, `number.py`, `text.py`,
  and `entity.py` (shared `grow_device_info`); constants `CTX_*`, `STAGE_OPTIONS`,
  `STAGE_TARGETS`, and `GROW_CONTEXT_LABELS` in `const.py`.
- **Platforms**: `select`, `number`, and `text` added to the integration's
  `PLATFORMS` list and forwarded per config entry.
- **Persistence**: Entities use Home Assistant restore state so operator-entered
  values survive restarts; no secrets are involved.
- **Consumption**: The AI health runtime reads these entities to enrich prompts;
  when unset, checks proceed without that context.
