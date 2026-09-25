## Why

Saving grow-space options replaces sensor and control mappings instead of merging them, and pump switches read `entry.data` while the options flow writes `entry.options`. After an options save the pump switch can keep an old outlet, a newly mapped pump can disappear, and a hidden water-role form can drop stored mappings. The live setup is LocalTuya on the LAN. Those local device bindings and the keys used to obtain them must survive every save. Cloud Tuya conductivity is unused and is not part of this change.

## What Changes

- Deep-merge sensor and control mappings on options save: start from the effective mappings, apply only the roles present on the form, and keep every role the form did not show.
- Every platform (switches, pump power, sensors) reads that same merged config.
- Preserve, and never blank, `water_monitor_device_id`, Tuya device ids, access id, and access secret when the operator saves options or the integration reloads.
- Do not read, write, or reload LocalTuya or Tuya Local config entries. Their `local_key` values stay where they are.
- Water chemistry for a bound local device continues to come from that device's Home Assistant entities. No cloud poll is started to "repair" chemistry.
- Leave `tuya_client` datapoint scaling untouched.

## Capabilities

### New Capabilities

- `local-key-preservation`: Options saves, reloads, and auto-bind must not drop the bound local water-monitor device or the stored Tuya identifiers and secrets used to obtain LAN keys, and must not modify LocalTuya / Tuya Local config.

### Modified Capabilities

- `grow-space-config`: Options flow deep-merges mappings, and runtime platforms consume the merged result rather than `entry.data` alone.

## Impact

- `config_flow.py` options submit and form defaults.
- `switch.py`, `sensor.py` pump setup and `_resolve_pump_power_source`.
- Shared merged-config helper used by `__init__.py` and platforms.
- Tests for options save with a bound LocalTuya device, a blank secret field, and a hidden water-role form.
- No change to `tuya_client.py` normalization. No new cloud polling.
