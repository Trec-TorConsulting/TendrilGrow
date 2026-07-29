## Why

TendrilGrow only models the flowering pipeline (seedling → flower → flush) and
assumes every plant is headed for "premium flower quality." The maintainer runs
the 3x3 as a dedicated **mothers** tent — plants kept in permanent vegetative
growth as clone stock that will never be flowered — and is adding a **Clone
King** cloner. Scoring mothers and clones against flower-quality targets is
wrong: mothers should be judged on vigor and compact structure, clones on
rooting. Growers also want to see where a crop sits in its full lifecycle and
when milestones (harvest, dry-done, cure-done) are projected.

## What Changes

- Expand the growth-stage select from the flower-only set to a full lifecycle:
  add `mother`, `clone`, `harvest`, `dry`, `cure`, and `ready` alongside the
  existing `seedling`, `vegetative`, `early_flower`, `mid_flower`,
  `late_flower`, and `flush`.
- Give each stage an **AI objective** so the health prompt is
  stage-appropriate: mothers judged on health/compactness (never flower),
  clones on rooting (high humidity, minimal nutrients), flowering stages remain
  quality-first, and post-harvest stages (dry/cure) assessed for
  drying/mold/trichomes rather than reservoir chemistry.
- Add per-stage reservoir targets (pH/EC/VPD) for `mother` and `clone`.
  Post-harvest stages carry no reservoir targets (the prompt already tolerates
  undefined targets).
- Add **default per-stage durations** and a **projected-timeline sensor** per
  grow space that derives days-in-stage, days-remaining, and projected
  stage-end / harvest / ready dates from the current stage and week-in-stage.
  Mothers are treated as indefinite (no projection).
- Keep `vegetative` as the default stage via a named constant (index-independent)
  since the option order changes. **Not breaking**: stored stages stay valid and
  new options are additive; no migration required.

## Capabilities

### New Capabilities
- `grow-lifecycle-projection`: default per-stage durations and a per-grow-space
  projection sensor exposing days-in-stage, days-remaining, and projected
  stage-end / harvest / ready dates, derived from the current stage and
  week-in-stage.

### Modified Capabilities
- `grow-cultivation-context`: the growth-stage select enumeration expands to the
  full lifecycle (adds `mother`, `clone`, `harvest`, `dry`, `cure`, `ready`),
  each stage carries an AI objective, and the default stage is pinned by name.
- `ai-health-monitoring`: the health prompt objective becomes stage-aware
  instead of always flower-quality-first, and tolerates stages that have no
  reservoir targets.

## Impact

- **Code**: `const.py` (`STAGE_OPTIONS`, `STAGE_TARGETS`, new `STAGE_OBJECTIVES`,
  `STAGE_DURATIONS_DAYS`, `DEFAULT_STAGE`), `select.py` (default by name),
  `ai/health_checks.py` (stage-aware objective line), a new projection sensor in
  `sensor.py`, i18n (`strings.json`, `translations/en.json`),
  `scripts/validate_live_ha.py` (recognize new stages), and tests.
- **Specs**: delta `grow-cultivation-context`, delta `ai-health-monitoring`,
  new `grow-lifecycle-projection`.
- **Live/UX**: the Growth Stage dropdown gains options and a projection sensor
  appears per grow space (dashboard cards can adopt it later). The Clone King is
  tracked by adding it as its own grow space with stage `clone`; its free-text
  `grow_type` already flows into the AI prompt. No breaking changes.
