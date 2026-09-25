## 1. Merged mappings

- [x] 1.1 Add a shared helper that deep-merges sensor and control mappings from form input onto the current merged config, updating only roles present on the form
- [x] 1.2 Use that helper in the options flow instead of replacing `sensor_mappings` and `control_mappings`
- [x] 1.3 Point `switch.py` setup and `_resolve_pump_power_source` at the merged config helper

## 2. Preserve local bindings and keys

- [x] 2.1 Treat a blank Tuya access id, access secret, device-id list, and water-monitor device id as "keep stored value"
- [x] 2.2 Change auto-bind so it writes `water_monitor_device_id` only when the merged value is empty, and never overwrites a stored id
- [x] 2.3 Confirm no code path in this change updates `localtuya` or `tuya_local` config entries or reads `local_key`
- [x] 2.4 Leave `tuya_client.py` datapoint scaling unchanged

## 3. Tests

- [x] 3.1 Options save with water roles hidden keeps the existing pH mapping
- [x] 3.2 Options save with a blank secret and blank device selector keeps the stored secret and `water_monitor_device_id`
- [x] 3.3 A pump mapped only in options creates a switch after reload
- [x] 3.4 Auto-bind does not replace an existing water-monitor device id
