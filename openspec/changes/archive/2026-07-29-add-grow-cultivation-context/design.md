# Design: add-grow-cultivation-context

## Context

AI health checks are far more accurate when grounded in operator context that
cannot be sensed automatically (stage, strain, nutrient plan, targets, reservoir
volume). This change (already implemented) exposes that context as editable HA
helper entities per grow space and wires it into the AI prompt. Documented here so
`openspec/specs/` matches shipped behavior.

Constraints:
- Async-only; entities restore their last value across restarts.
- Context is per grow-space config entry and grouped under its device.
- No secrets; values are user-visible operational metadata.

## Goals / Non-Goals

**Goals:**
- Let operators edit cultivation context directly in Home Assistant.
- Persist values across restarts.
- Make context discoverable by the AI health runtime via a stable label map.

**Non-Goals:**
- Automating stage transitions or feed scheduling (future automations change).
- Historical logging/graphing of context (dashboards change).

## Decisions

### Restore-state helper entities
`GrowStageSelect` uses `RestoreEntity`, `GrowContextNumber` uses `RestoreNumber`,
and `GrowContextText` uses `TextEntity` + `RestoreEntity`. Rationale: operator
input must survive restarts without external storage.

### Stable unique-id suffixes + label map
Each context entity's unique id ends with a `CTX_*` suffix; `GROW_CONTEXT_LABELS`
maps each suffix to a prompt label. The AI runtime enumerates the entry's registry
entities and reads matching states. Rationale: decouples the prompt from entity
ids and lets context be optional.

### Per-stage target ranges
`STAGE_TARGETS` encodes pH/EC/VPD ranges per stage for scoring calibration; the
operator can tune them in code. Rationale: gives the model concrete, stage-aware
targets instead of generic guidance.

### Grouped under the grow-space device
All context entities share `grow_device_info` so they appear under the grow
space's device. Rationale: keeps each space's context together in the UI.

## Risks / Trade-offs

- **Unset context reduces advice quality** → checks still run; the prompt notes
  missing context and the model lowers confidence.
- **Static `STAGE_TARGETS`** → acceptable for now; a future change can make them
  user-editable per space.

## Migration Plan

Additive — new entities appear for each grow space after setup; defaults are
sensible and editable. No data migration required.
