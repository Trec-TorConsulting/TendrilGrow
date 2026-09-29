## Context

`GrowSpace.targets` and `schedules` are stored on the config entry and default to `{}`. The AI prompt JSON-dumps them. Operators already edit a single target pH, target EC, and lights-on hours as cultivation-context numbers. They cannot set a band (low/high) or a clock time for lights. `STAGE_TARGETS` is the only band source.

This change adds the missing band and schedule helpers. It does not change how water sensors are read and does not touch LocalTuya keys.

## Goals / Non-Goals

**Goals:**

- Editable pH, EC, and VPD low/high per grow space, seeded from the current stage when the operator has not set them.
- A lights-on time and a lights-off time, with lights-on hours kept in sync as the duration.
- AI prompt and band alerts read these entities.

**Non-Goals:**

- Turning the lights on or off at those times (`add-automations-engine`).
- Per-strain duration tables.
- Rewriting stage-table defaults in `const.py` beyond using them as seeds.

## Decisions

### Entities, not the empty dict

Add number entities: `target_ph_low`, `target_ph_high`, `target_ec_low`, `target_ec_high`, `target_vpd_low`, `target_vpd_high`. Add two time helpers for lights on and lights off (`time` platform, or text HH:MM if the time platform is a larger jump — prefer `time` entities). Existing single `target_ph` and `target_ec` numbers remain and, when the operator edits them, set the midpoint is not required; the band entities are the new source. On first setup, if the band entities have no restored state, seed low/high by parsing `STAGE_TARGETS` for the current stage.

### Do not clobber overrides on stage change

Changing stage already resets stage-started to today. It MUST NOT overwrite a band the operator has changed. Track an `overridden` flag per band in restore extra data (true after the first operator write). Stage change reseeds only bands that are not overridden.

### Prompt

`_build_prompt` includes the active band and the light on/off times in cultivation context. The empty `targets` / `schedules` JSON may remain for compatibility but must not be the only place those values appear.

### Hours stay consistent

When both clock times are set, `lights_on_hours` updates to the duration, including an overnight span (off after midnight). Editing `lights_on_hours` does not invent clock times.

## Risks / Trade-offs

- [More entities on an already busy device] → Group them with the cultivation context and use entity categories so the primary dashboard stays quiet.
- [Stage reseed surprises the operator] → Only untouched bands reseed, and the stage-change behavior for the date stays as it is.

## Migration Plan

New unique ids. Restored state means existing installs get seeds on first run after upgrade, then operator edits stick. No config entry version change.

## Open Questions

None.
