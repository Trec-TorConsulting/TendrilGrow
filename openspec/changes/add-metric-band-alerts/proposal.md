## Why

Stage bands for pH, EC, and VPD already exist and are only pasted into the AI prompt. A reservoir can drift for hours between vision checks. Growers need a notify-only signal when a live local reading leaves the band, without a rules engine and without actuating pumps or lights.

## What Changes

- Compare live pH, EC, and canopy VPD to the current stage's target band (operator targets override the stage default when set).
- Expose a problem binary sensor per metric and a single "out of range" summary.
- Notify through the existing AI notify service when a band is breached, with a per-metric cooldown so a stuck reading does not spam.
- Readings come from mapped entities. For water metrics on a LocalTuya-bound space, that is the local device's sensors. This change does not poll Tuya cloud and does not read or write local keys.

## Capabilities

### New Capabilities

- `metric-band-alerts`: Notify-only pH, EC, and VPD band alerts with cooldown, fed by mapped local sensors and stage or operator targets.

### Modified Capabilities

## Impact

- New monitor module, binary sensors, and a small amount of notify wiring in `__init__.py`.
- Uses `STAGE_TARGETS` and, when `add-grow-targets` lands, operator target entities.
- No pump, light, or fan commands. `add-automations-engine` stays the place for actuation.
- No changes to `tuya_client.py` or LocalTuya config entries.
