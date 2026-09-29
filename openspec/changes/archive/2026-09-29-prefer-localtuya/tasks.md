# Tasks: prefer-localtuya

> Implementation complete, including live HA verification (6.3). TendrilGrow consumes
> LocalTuya / Tuya Local entities; it does not speak the Tuya LAN protocol.

## 1. Constants and source helpers

- [x] 1.1 Add `CONF_WATER_MONITOR_DEVICE_ID` and local-integration domain constants (`localtuya`, `tuya_local`) in `const.py`
- [x] 1.2 Add a water-role tuple for local auto-map (`ph`, `ec`, `cf`, `orp`, `tds`, `water_temperature`) that excludes canopy `temperature` / `humidity`
- [x] 1.3 Add `effective_water_source(hass, entry)` returning `localtuya` | `tuya_local` | `cloud` | `none` (local bind wins over `tuya_enabled`)

## 2. Local device resolver

- [x] 2.1 Resolve a bound HA device id from entry data/options; look up the device registry and accept only `localtuya` / `tuya_local` identifier domains (`localtuya` first)
- [x] 2.2 If unbound, match `CONF_TUYA_DEVICE_IDS` against registry identifiers; persist the HA device id only on a unique match; never guess among multiple probes
- [x] 2.3 Classify sensors on the bound device (device_class, unit, then name) into water roles; skip humidity, canopy temperature, battery, and config/number entities
- [x] 2.4 Unit-test unique match, ambiguous match, domain priority, and sensor classification (`tests/test_local_water_source.py`)

## 3. Auto-map and coordinator gating

- [x] 3.1 On grow-space setup, auto-map unmapped water roles from the bound local device into `grow_space.sensor_mappings` and `auto_mapped_sensor_roles`; do not override existing mappings
- [x] 3.2 Start `TendrilGrowTuyaCoordinator` and create `TuyaMetricSensor` / last-updated entities only when effective source is `cloud`
- [x] 3.3 Move VPD and AI health sensor construction out of the `tuya_enabled` block so they exist when cloud polling is off
- [x] 3.4 Stop auto-mapping cloud `ambient_humidity` / ambient temperature onto canopy roles
- [x] 3.5 `rebuild_automap` reloads entries so local-device matching and auto-map run again
- [x] 3.6 Unit-test: local bind skips coordinator; cloud fallback still creates Tuya sensors; existing mappings are preserved; humidity is not auto-mapped

## 4. Config and options flow

- [x] 4.1 Add a water-monitor device selector (devices whose identifier domain is `localtuya` or `tuya_local`) on the mapping step; persist `CONF_WATER_MONITOR_DEVICE_ID`
- [x] 4.2 Show water-quality mapping fields when a local device is bound (or neither source is active); hide them only for cloud-fallback-with-no-local-device
- [x] 4.3 Keep cloud Tuya fields as optional fallback; new entries default `tuya_enabled` false
- [x] 4.4 Add `strings.json` / `translations/en.json` labels for the device selector and fallback copy (both files in sync)
- [x] 4.5 Unit-test selector persistence, water-field visibility, and default-off cloud polling (`tests/test_config_flow.py`)

## 5. Diagnostics and docs

- [x] 5.1 Include `water_source` and bound HA device id in diagnostics; keep `tuya_access_secret` redacted
- [x] 5.2 Rewrite `docs/tuya-water.md` (and install/configuration/troubleshooting/README companion list) so LocalTuya is the recommended path and IoT Core is key-extraction only
- [x] 5.3 Note dashboard entity-id churn when cloud Tuya sensors go away; point at `scripts/generate_dashboard.py`
- [x] 5.4 CHANGELOG: prefer LocalTuya; cloud polling is fallback-only

## 6. Validation

- [x] 6.1 Full test pass for resolver, auto-map, config flow, and diagnostics
- [x] 6.2 `ruff check .` clean
- [x] 6.3 Live check: bind each tent's LocalTuya (or Tuya Local) probe; confirm pH/EC/TDS/water temp map correctly, VPD still uses canopy air sensors, and no OpenAPI polls appear in logs for those entries
