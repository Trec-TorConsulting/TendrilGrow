## Context

Cultivation context is modeled as restore-on-restart helper entities (`select`,
`number`, `text`) under each grow-space device, discovered by AI via
`GROW_CONTEXT_LABELS`. Operators already set stage, nutrients, and reservoir
targets; source water type is the missing makeup-water signal for RDWC fills
and flushes.

Constraints:
- Match existing helper patterns (RestoreEntity, `grow_device_info`, snake_case
  values + human labels)
- Context must remain optional for AI (unset omitted); a sensible default is OK
  for the select itself
- No config-entry / options-flow fields for cultivation plan values

## Goals / Non-Goals

**Goals:**
- Let operators declare makeup water type per grow space
- Persist across restarts and expose it to AI health prompts
- Give the model enough water-source grounding for Cal-Mag / baseline-EC advice

**Non-Goals:**
- Measuring source-water EC/pH/TDS (use mapped sensors if the operator has them)
- Automating RO system / fill valves
- Per-source mineral profiles or hardness inputs (future enhancement)
- Changing flush-tracking mechanics (interval / Flush Now)

## Decisions

### Second select helper (not free-text)
Add `GrowWaterTypeSelect` alongside `GrowStageSelect` with a fixed option set.
Rationale: AI and UI need stable values; free-text invites typos and weak
grounding. Alternatives considered: text entity (rejected — no stable enum),
config-entry option (rejected — cultivation plan is helpers, not entry data).

### Default = `tap`
Default current option to `tap` by name (same “default by name” pattern as
stage). Rationale: most operators start on municipal or well tap; they can
change immediately. Alternatives: no default / unknown — HA selects usually
need a current option.

### Option set (snake_case)
`tap`, `ro`, `filtered`, `bottled`, `rain`, `well`, `distilled`, `spring`,
`mixed`. Labels: Tap, RO, Filtered, Bottled, Rain, Well, Distilled, Spring,
Mixed. No catch-all `other` for now — `mixed` covers blends; revisit if users
need a free-form escape hatch.

### Prompt label `water_type`
Map `CTX_WATER_TYPE` → `water_type` in `GROW_CONTEXT_LABELS` so the collector
picks it up automatically. Add a short dosing clause when present (RO /
distilled / rain → expect near-zero mineral baseline and Cal-Mag; tap / well /
spring → account for baseline minerals / chlorine; filtered / bottled / mixed →
treat as intermediate and ask if unclear).

## Risks / Trade-offs

- **Tap default may be wrong for RO-only growers** → easy one-tap change; value
  appears in the Cultivation Plan device
- **Coarse enum oversimplifies “filtered” / “bottled”** → acceptable; mineral
  profile inputs can come later if needed
- **Prompt guidance is heuristic** → keep brief; operator targets still win

## Migration Plan

Additive entity on next reload/setup. No data migration. Existing spaces get
the select at default `tap` until changed.

## Open Questions

- None for v1; defer source-water EC/hardness numeric context to a later change
  if AI advice still under-grounds.
