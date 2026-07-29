## 1. Stage constants and metadata (`const.py`)

- [x] 1.1 Add `DEFAULT_STAGE = "vegetative"` and expand `STAGE_OPTIONS` to the full lifecycle in order: `seedling, mother, clone, vegetative, early_flower, mid_flower, late_flower, flush, harvest, dry, cure, ready`
- [x] 1.2 Add `STAGE_TARGETS` entries — `mother` (pH 5.8–6.2, EC 1.0–1.6, VPD 0.8–1.1) and `clone` (pH 5.5–6.0, EC 0.0–0.4, VPD 0.4–0.8); leave harvest/dry/cure/ready without targets
- [x] 1.3 Add `DEFAULT_OBJECTIVE` (current quality-first flower text) and `STAGE_OBJECTIVES` with stage-specific objectives for `clone`, `mother`, `harvest`, `dry`, `cure`, `ready`
- [x] 1.4 Add `STAGE_DURATIONS_DAYS` defaults (clone 10, seedling 14, vegetative 28, early_flower 21, mid_flower 14, late_flower 21, flush 10, harvest 1, dry 10, cure 21; `mother`/`ready` = None) and `STAGE_PIPELINE` (biological order for projection)

## 2. Growth-stage select and labels (`select.py`, i18n)

- [x] 2.1 Use `DEFAULT_STAGE` (by name) for the initial/current option instead of `STAGE_OPTIONS[1]`
- [x] 2.2 Set `_attr_translation_key = "growth_stage"` on `GrowStageSelect`
- [x] 2.3 Add a `select.growth_stage.state` label map for every stage in `strings.json` and `translations/en.json` (Seedling, Mother, Clone, Vegetative, … Ready)

## 3. Stage-aware AI prompt (`ai/health_checks.py`)

- [x] 3.1 Resolve `objective = STAGE_OBJECTIVES.get(stage, DEFAULT_OBJECTIVE)` and replace the hard-coded "premium flower quality" opening with an agronomist role plus a "Primary objective for the '<stage>' stage: …" line
- [x] 3.2 Confirm stages without `STAGE_TARGETS` still build a valid prompt via the existing "targets not defined" fallback

## 4. Projected timeline sensor (`sensor.py`)

- [x] 4.1 Add a projection helper that reads the grow space's `growth_stage` select and `week_in_stage` number states and computes `days_in_stage`, `days_remaining`, `projected_stage_end`, `projected_harvest_date`, `projected_ready_date` from `STAGE_DURATIONS_DAYS` + `STAGE_PIPELINE`
- [x] 4.2 Add `TendrilGrowStageProjectionSensor` (state = days remaining, unit `d`; attributes for stage, days_in_stage, days_remaining, projected dates, pipeline_position; grouped on the grow device; `unknown` for `mother`/`ready`) and subscribe to the source entities' state changes
- [x] 4.3 Register the projection sensor in `async_setup_entry` independent of Tuya configuration

## 5. Live validation (`scripts/validate_live_ha.py`)

- [x] 5.1 Recognize the new stage values and report the stage-projection sensor when present

## 6. Tests

- [x] 6.1 Assert stage invariants: every `STAGE_OPTIONS` entry has an i18n label; `DEFAULT_STAGE` is in options; `STAGE_PIPELINE` covers all bounded stages; `mother`/`ready` have no duration
- [x] 6.2 Assert the select default resolves to `vegetative` regardless of option order
- [x] 6.3 Assert the AI prompt objective is stage-aware — non-flower framing for `mother`, `clone`, and a post-harvest stage
- [x] 6.4 Assert projection math: days-remaining and projected harvest/ready dates for a pre-harvest stage; `unknown` for `mother` and `ready`

## 7. Validation and docs

- [x] 7.1 `openspec validate add-grow-lifecycle-stages --strict` passes
- [x] 7.2 `ruff check .`, `ruff format .`, and `pytest -q` all pass
- [x] 7.3 Update the README cultivation/stages note to mention the lifecycle stages and projection sensor
