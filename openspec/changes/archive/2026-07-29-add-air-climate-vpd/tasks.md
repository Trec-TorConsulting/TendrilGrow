# Tasks: add-air-climate-vpd

> Implemented correctness fix. All tasks complete and verified (31 tests pass,
> ruff clean, live validator confirms unit-aware VPD and water-temp guidance).

## 1. Roles and config

- [x] 1.1 Add `SENSOR_ROLE_WATER_TEMPERATURE` to `const.py`; include it in `SENSOR_ROLES` and `SENSOR_ROLES_CONFIGURABLE`
- [x] 1.2 Make air `temperature`/`humidity` visible under Tuya (`SENSOR_ROLES_TUYA_OPTIONAL`)
- [x] 1.3 Remap Tuya `water_temp_c` metric to `water_temperature` (was `temperature`) in `sensor.py`

## 2. Unit-aware VPD

- [x] 2.1 Add `GrowSpace.to_celsius(value, unit)` and `GrowSpace.compute_vpd_kpa(temp, unit, humidity)`
- [x] 2.2 Add a VPD sensor entity (kPa) computed from mapped air temp + air humidity; unavailable when inputs missing
- [x] 2.3 Group the VPD sensor on the grow-space device; track source entities and recompute on change

## 3. AI prompt and i18n

- [x] 3.1 Collect metric units; label metrics (Air Temperature / Air Humidity / Water Temperature …) with units; add a derived VPD line
- [x] 3.2 Relabel `temperature`/`humidity` as AIR in `strings.json`/`translations/en.json`; add `water_temperature`

## 4. Validation

- [x] 4.1 Unit tests: `to_celsius`, unit-aware `compute_vpd_kpa`, updated prompt + options-flow expectations
- [x] 4.2 `ruff check .` clean; full test suite passes
- [x] 4.3 Live validator: unit-aware VPD + `water_temperature` reporting + air-temp guidance
