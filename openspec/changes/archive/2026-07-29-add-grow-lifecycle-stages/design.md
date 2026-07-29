## Context

Today `STAGE_OPTIONS` in `const.py` holds six flower-pipeline stages
(`seedling`, `vegetative`, `early_flower`, `mid_flower`, `late_flower`,
`flush`). `STAGE_TARGETS` maps each to pH/EC/VPD ranges that calibrate the AI
prompt, which is hard-coded as a "master cannabis cultivation agronomist
specializing in premium flower quality." `GrowStageSelect` (a `RestoreEntity`)
stores the raw stage string and defaults to `STAGE_OPTIONS[1]`. `week_in_stage`
is an operator-entered number; `grow_type` is free-text per grow space.

Constraints: the select persists a raw string (no entity migration wanted), new
options must be additive, post-harvest stages have no reservoir chemistry, and
the maintainer's live setup is the validation source (3x3 mothers tent; a Clone
King cloner coming soon).

## Goals / Non-Goals

**Goals:**
- A full lifecycle stage set with correct AI framing per stage.
- `mother` = permanent vegetative (never flower); `clone` = rooting cuttings.
- Reservoir targets for `mother`/`clone`; graceful no-target for post-harvest.
- Projected timings derived from the current stage and `week_in_stage`.
- Friendly dropdown labels; no breaking change and no data migration.

**Non-Goals:**
- Auto-advancing stages (the operator sets stage manually).
- Per-strain duration editing UI (ship constants now; tunable entities later).
- Drying/curing environmental control or a separate temp/RH target schema.
- New dashboard cards (adopt the projection sensor in a later change).

## Decisions

### 1. Model the lifecycle as select stages, not a new "grow type"
The lifecycle is a per-plant temporal state, so it belongs on the growth-stage
select. `grow_type` stays free-text for the system/method (e.g. "RDWC", "Clone
King / aeroponic cloner") and already flows into the AI prompt. The Clone King
is tracked by adding it as its own grow space with stage `clone`. Alternative
(a dedicated grow-type enum) rejected: targets, objectives, durations, and
projection all key off the temporal stage, not the method.

### 2. Canonical values, order, and default
Values stay snake_case: `seedling, mother, clone, vegetative, early_flower,
mid_flower, late_flower, flush, harvest, dry, cure, ready`. Dropdown order
follows the operator's mental model (mother/clone near the top). Because the
order changes, the default moves from `STAGE_OPTIONS[1]` to a named constant
`DEFAULT_STAGE = "vegetative"` that `select.py` uses directly (a unit test pins
this). All previously stored values remain members of the new set, so no
migration is needed.

### 3. Reservoir targets (`STAGE_TARGETS`)
Add live-plant chemistry for the two new hydroponic stages:
- `mother`: pH 5.8–6.2, EC 1.0–1.6 mS/cm, VPD 0.8–1.1 kPa (steady moderate feed,
  compact and healthy, never flower).
- `clone`: pH 5.5–6.0, EC 0.0–0.4 mS/cm, VPD 0.4–0.8 kPa (high humidity, minimal
  nutrients, stable pH).

`harvest`, `dry`, `cure`, `ready` are intentionally omitted; the prompt's
existing "targets not defined; infer from best practice" fallback plus the stage
objective (Decision 4) covers them.

### 4. Stage-aware AI objective (`STAGE_OBJECTIVES`)
Introduce `STAGE_OBJECTIVES: dict[str, str]`. `_build_prompt` selects
`STAGE_OBJECTIVES.get(stage, DEFAULT_OBJECTIVE)` and emits a "Primary objective
for the '<stage>' stage: …" line, replacing the unconditional "premium flower
quality" framing. `DEFAULT_OBJECTIVE` preserves today's quality-first flower
guidance for `seedling`/`vegetative`/`*_flower`/`flush`. Special objectives:
- `clone`: unrooted cuttings — goal is rooting; keep humidity very high (low
  VPD), nutrients minimal, pH stable; watch wilting/damping-off/rot; do not
  assess flowering or yield.
- `mother`: permanent veg stock — never flower; prioritise long-term health,
  compact bushy structure with many clone sites, steady moderate feed; avoid
  stretch/burn/stress.
- `harvest`/`dry`/`cure`/`ready`: post-harvest — assess drying/curing (target
  air temp/RH, mould, trichome colour, stem snap / jar RH), not reservoir
  chemistry.

Alternatives rejected: branching the entire prompt per stage (duplication) or a
per-stage template file (maintenance cost). A single injected objective line is
the smallest change that makes the model stage-correct.

### 5. Projected timings (`grow-lifecycle-projection`)
- `STAGE_DURATIONS_DAYS` defaults (operator-tunable in a later change),
  confirmed against Leafly's growth-stage and drying/curing guides (2025):
  `clone 10, seedling 14, vegetative 28, early_flower 21, mid_flower 14,
  late_flower 21, flush 10, harvest 1, dry 10, cure 21`. `mother` and `ready`
  are indefinite/terminal (`None`). Sources: seedling 2–3 wk, veg 3–16 wk,
  flower 8–11 wk (subphases wk 1–3 / 4–5 / 6+), dry ~7–14 days for a slow
  quality dry, cure 2–4 wk minimum.
- Projection pipeline (biological order, distinct from dropdown order):
  `clone → seedling → vegetative → early_flower → mid_flower → late_flower →
  flush → harvest → dry → cure → ready`. `mother` is off-pipeline.
- Derivation: `days_in_stage = week_in_stage × 7` (0 if unset);
  `days_remaining = max(0, duration − days_in_stage)`;
  `projected_stage_end = now + days_remaining`;
  `projected_harvest_date` / `projected_ready_date = now + days_remaining +
  Σ durations of pipeline stages between the current stage and `harvest`/`ready`.
- Exposure: one sensor per grow space, `sensor.<space>_stage_projection`. State
  is `days_remaining` (unit `d`) — always meaningful for pipeline stages, and
  `unknown` for `mother`/`ready`. Attributes carry `stage`, `days_in_stage`,
  `days_remaining`, `projected_stage_end`, `projected_harvest_date`,
  `projected_ready_date`, and `pipeline_position`. A single rich sensor keeps
  entity sprawl down; discrete sensors can be split out later if wanted.

### 6. `week_in_stage` is the clock
Reuse the existing operator number instead of adding a stage-start timestamp, so
no new required input is introduced. Trade-off: projection accuracy depends on
the operator resetting `week_in_stage` on each stage change (documented).

### 7. Friendly dropdown labels
Give `GrowStageSelect` a `translation_key` and add a select-state map in
`strings.json` / `translations/en.json` so options render as "Seedling",
"Mother", "Clone", … while stored values stay snake_case slugs.

## Risks / Trade-offs

- Operator must reset `week_in_stage` on stage change → projection is advisory;
  a future change can add an automatic stage-start timestamp.
- Default durations are strain/environment dependent → ship sane defaults as
  constants, note they are estimates, make them tunable in a later change.
- Post-harvest stages lack reservoir targets → prompt fallback + objective steer
  the AI to drying/curing assessment instead of pH/EC.
- Reordering options could change the default → default pinned by name and
  covered by a unit test.

## Migration Plan

Additive; no data migration. Every previously stored stage value is still a
member of the new set. The projection sensor appears automatically. Rollback is
a code revert; a stage newly set to `mother`/`clone`/`harvest`/`dry`/`cure`/
`ready` would display raw under the old option set until re-selected — acceptable.

## Open Questions

- Projection state: resolved — `days_remaining` (numeric, unit `d`).
- Default durations: confirmed against Leafly (2025); `mid_flower` set to 14 and
  `dry` to 10 to match sourced sub-phase and slow-dry ranges.
- Dashboard: resolved — add the projection card now (Executive + per-tent).
