## Why

Total pump power subscribes to guessed entity ids (`sensor.{entry_id}_{role}_power`) that Home Assistant never creates, so the sum stays unavailable and daily cost has nothing to read. Daily cost also multiplies instantaneous watts by 24 hours, which overstates pumps that cycle.

## What Changes

- Resolve each per-pump power sensor through the entity registry by `unique_id`, and subscribe the total sensor to those real entity ids.
- Estimate daily energy from observed on-time (or integrated power), not a fixed 24-hour assumption. Keep the estimate labeled as an estimate.
- Pump switches and power resolution use the merged mappings from `fix-mapping-preservation`.

## Capabilities

### New Capabilities

- `pump-power-accounting`: Total pump power tracks the real per-pump sensors, and daily energy reflects duty cycle.

### Modified Capabilities

## Impact

- `sensor.py` total pump power subscription and `TendrilGrowEnergyCostSensor`.
- `insights.py` `compute_daily_energy_kwh` callers.
- Tests that create pump power sensors and assert the total and cost update when a pump is off part of the day.
- Depends on merged mappings so a pump configured in options is included.
