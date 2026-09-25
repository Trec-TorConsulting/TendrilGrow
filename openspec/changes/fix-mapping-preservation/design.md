## Context

One config entry is one grow space. Create stores mappings and Tuya fields on `entry.data`. The options flow builds a new `sensor_mappings` and `control_mappings` dict from the fields on that form and stores them on `entry.options`. Setup merges with `dict.update`, so the options dict replaces the data dict entirely. Roles hidden because cloud fallback is selected never appear in the form and are dropped.

Pump switches and pump-power resolution read `entry.data` only, so they ignore options.

The live water path is LocalTuya (LAN). LocalTuya keeps each probe's `local_key` in its own config entry. TendrilGrow stores the HA `water_monitor_device_id` plus the IoT Core access id, access secret, and device ids that were used once to obtain those LAN keys. Cloud polling is not the water source in this setup, and cloud datapoint scaling is not being fixed.

## Goals / Non-Goals

**Goals:**

- Options save deep-merges mappings and preserves every role the form did not display.
- Switches, sensors, and services read one merged config.
- A blank secret field, a reload, and auto-bind never clear `water_monitor_device_id`, Tuya device ids, access id, or access secret.
- TendrilGrow never writes LocalTuya or Tuya Local config entries.

**Non-Goals:**

- Changing `tuya_client.py` conductivity, CF, or TDS scaling.
- Enabling, scheduling, or "repairing" Tuya cloud polling.
- Deleting stored cloud credentials. They stay so the LAN keys can be recovered.
- Implementing the Tuya LAN protocol inside TendrilGrow.

## Decisions

### Deep-merge mappings, do not replace the dict

On options submit, start from the current merged `sensor_mappings` and `control_mappings`. For each role that was actually on the form, set it when the user picked an entity and remove it when they cleared it. Roles absent from the form stay as they were.

Alternative considered: keep writing a full replacement dict and also render every hidden role as a hidden form field. Rejected — a missed field still wipes data. Merge is safe when the form is partial.

### One merged-config helper

Platforms call the same helper `__init__.py` already uses (`data` then `options`). `switch.py` and `_resolve_pump_power_source` stop reading `entry.data` alone.

### Secret and device-id fields use "blank means keep"

`tuya_access_secret` already does this. Apply the same rule to access id, device ids, and `water_monitor_device_id`: an omitted or blank value keeps the stored value. Clearing a binding requires an explicit clear control, not an empty selector.

Auto-bind may set `water_monitor_device_id` when it is empty and exactly one local device matches the stored Tuya device ids. It must not overwrite a stored device id and must not update any other key.

### Do not touch companion integrations

Local keys live in LocalTuya / Tuya Local. This change does not call `async_update_entry` on those domains, does not read `local_key` into TendrilGrow storage, and does not log it.

### Water chemistry stays on the bound local device

When `water_monitor_device_id` resolves to a `localtuya` or `tuya_local` device, water roles come from that device's entities. This change does not start `TendrilGrowTuyaCoordinator` as part of the fix.

## Risks / Trade-offs

- [Options previously relied on replacement to delete a mapping] → A role that is on the form and submitted empty is removed. Roles not on the form are kept. Document that in the options form.
- [Auto-bind writes `entry.data` while options hold a newer device id] → Auto-bind reads the merged id and only persists when the merged id is empty.
- [Someone later "cleans up" unused cloud credentials] → Spec forbids deleting access id, secret, and device ids in this change. Recovery of LAN keys depends on them.

## Migration Plan

No config-entry version bump. The next options save rewrites options with a merged mapping dict; until then, platforms reading the merged helper already see `options` over `data`. Reload each grow space after upgrade so switches pick up the helper. Rollback is reverting the integration; stored keys are not modified by the upgrade itself.

## Open Questions

None. Cloud conductivity stays out of scope by operator decision.
