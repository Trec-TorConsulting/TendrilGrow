## Context

Per-pump power sensors use `unique_id` `{entry_id}_{pump_role}_power`. Home Assistant assigns `entity_id` from the device name. The total sensor subscribes to `sensor.{entry_id}_{pump_role}_power`, which is not that entity id, so the sum never updates. Daily cost looks up the total by registry id (correct) and then multiplies watts by 24 hours.

Pump setup currently reads `entry.data`. It must use the merged mappings from `fix-mapping-preservation`.

## Goals / Non-Goals

**Goals:**

- Total pump power follows the live per-pump power sensors.
- Daily energy uses observed duty cycle for the local day, still marked estimated.
- Power resolution uses merged control and sensor mappings.

**Non-Goals:**

- Utility-meter tariffs or the Home Assistant Energy dashboard.
- Controlling pumps. Actuation stays manual.
- Cloud Tuya or local-key handling.

## Decisions

### Registry lookup, same as the cost sensor

When subscribing, resolve `sensor` / `tendrilgrow` / `{entry_id}_{pump_role}_power` through the entity registry. Subscribe to that `entity_id`. If the entity is not registered yet, subscribe on `async_added_to_hass` after a short retry or track the registry. Do not guess `entity_id` from `entry_id`.

Alternative considered: set `entity_id` explicitly to the guessed form. Rejected — it fights the entity registry and breaks if the user renamed the entity.

### Duty cycle from the pump switch

For each mapped pump, treat power as the current watt reading while the proxy switch is on and as zero while it is off. Integrate on-time across the local day: energy (kWh) = sum over pumps of (watts × hours-on-today) / 1000. If a pump has power but no switch state, fall back to the current watts and expose `duty_cycle_known: false` so the cost is not presented as a full-day fact without saying so.

Alternative considered: Riemann-sum the power sensor history via `recorder`. More accurate, and it requires history to be enabled. Switch on-time is available without recorder and matches the dosing workflow (pump off while mixing). Use switch on-time first.

### Hours-on resets at local midnight

Store `turned_on_at` in runtime and add elapsed on-time into a daily counter when the switch turns off or when the day rolls. Persist the counter in the same Store pattern as flush state so a restart mid-day does not zero the estimate. Mark the attribute `estimated: true`.

## Risks / Trade-offs

- [Switch state missing at restart] → Assume the switch's restored state and start the on-interval at startup, and label the day partial via `observed_since`.
- [Power sensor updates slower than the switch] → Use the last known watts while on. A brief spike is acceptable for a cost estimate.
- [Mapping fix not applied yet] → This change also reads merged config so it is correct on its own.

## Migration Plan

No unique_id changes, so entity history is kept. After upgrade, total power should become available on the next power update. Daily cost changes meaning from "24h at current watts" to "today's on-time"; release notes must say that.

## Open Questions

None.
