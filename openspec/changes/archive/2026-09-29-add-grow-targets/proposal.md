## Why

Each grow space stores `targets` and `schedules`, and the AI prompt dumps them, but both default to empty and nothing in the UI edits them. Stage tables in code are the only calibration. Operators need to set pH, EC, VPD, and the light schedule per space without editing YAML.

## What Changes

- Add restore-state number entities for target pH low/high, target EC low/high, and target VPD low/high, seeded from the current stage table.
- Add a lights-on and lights-off time (or keep lights-on hours and add an on-time) so the photoperiod is an operator setting, not only a duration.
- Feed those values into the AI prompt and into metric band alerts instead of the empty `targets` / `schedules` dicts.
- Stage changes refresh the suggested defaults only when the operator has not overridden that target.

## Capabilities

### New Capabilities

- `grow-target-schedule`: Editable per-space pH, EC, and VPD bands plus a light schedule, used by the AI prompt and band alerts.

### Modified Capabilities

- `grow-cultivation-context`: Cultivation context includes the operator target band and light schedule, not only the hardcoded stage table.

## Impact

- `number.py` or `select.py` / `text.py` for the new helpers, `const.py` labels, strings, and `ai/health_checks.py` prompt assembly.
- `models/grow.py` continues to store targets; the entities become the source of truth and write back.
- Does not change water-source selection or any Tuya / LocalTuya credential.
