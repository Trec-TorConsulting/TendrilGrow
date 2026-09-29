# Tasks: add-pump-power-control

> Forward-looking change — **not yet implemented**. Work top to bottom; each task is
> independently verifiable. This change adds **manual** control + monitoring only; it
> performs no automatic actuation. Do not check a box until its verification passes.

## 1. Constants and roles

- [x] 1.1 Add `CONTROL_ROLE_RDWC_PUMP`, `CONTROL_ROLE_CHILLER_PUMP`, `CONTROL_ROLE_AIR_PUMP`; append them to `CONTROL_ROLES`; add `PUMP_CONTROL_ROLES` subset (`const.py`)
- [x] 1.2 Add power-sensor role constants (`rdwc_pump_power`, `chiller_pump_power`, `air_pump_power`), the `PUMP_POWER_ROLE_FOR` map, and `PUMP_LABELS` (`const.py`)
- [x] 1.3 Confirm `GrowSpace.bind_control` accepts the new roles (they are in `CONTROL_ROLES`) and `from_dict` round-trips pump mappings (add/adjust `tests/test_grow_model.py`)

## 2. Options flow (mapping)

- [x] 2.1 Show pump control roles in the options control-mapping section using a `switch`/`input_boolean`-domain-limited entity selector (`config_flow.py`)
- [x] 2.2 Add optional power-sensor fields per pump (`sensor` domain); persist non-empty values under `sensor_mappings` with the `*_power` role keys (`config_flow.py`)
- [x] 2.3 Reload the entry on save so proxy entities are added/removed to match the new mappings
- [x] 2.4 Unit-test: submitting pump switch + power mappings stores them; clearing a field removes it (`tests/test_config_flow.py`)

## 3. Proxy switch platform

- [x] 3.1 Add `switch.py` with `async_setup_entry` creating one `TendrilGrowPumpSwitch` per **mapped** pump role, attached to the grow-space `DeviceInfo`; add `switch` to `PLATFORMS` (coordinate with `add-automations-engine` if `switch.py` already exists)
- [x] 3.2 Implement `is_on` (mirror mapped entity) and `available` (False when mapped entity missing/`unavailable`/`unknown`)
- [x] 3.3 Implement `async_turn_on`/`async_turn_off`/`async_toggle` with domain routing (`switch`, `input_boolean`, `homeassistant` fallback)
- [x] 3.4 Subscribe to the mapped entity via `async_track_state_change_event`; write state on change; unsubscribe on remove
- [x] 3.5 Unit-test state mirroring, availability, and turn routing by domain (`tests/test_switch.py`)

## 4. Power monitoring

- [x] 4.1 Implement power-source resolution: explicit `*_power` mapping first, else auto-discover a `device_class: power` sensor on the pump switch's device via the entity registry (`power.py` or a `sensor.py` helper)
- [x] 4.2 Add a per-pump `sensor.<grow>_<role>_power` (`device_class: power`, `W`) mirroring the resolved source; `unavailable` when the source is
- [x] 4.3 Add `sensor.<grow>_total_pump_power` summing currently-available per-pump power values
- [x] 4.4 (Optional) If a source energy sensor is found, expose `sensor.<grow>_<role>_energy` (`device_class: energy`, `kWh`, `total_increasing`)
- [x] 4.5 Unit-test source resolution (explicit + auto-discovery), mirroring, and the total sum (`tests/test_pump_power.py`)

## 5. Control service

- [x] 5.1 Register `tendrilgrow.set_pump` (`entry_id`, `pump`, `action`) and document fields in `services.yaml`
- [x] 5.2 Resolve the entry's `GrowSpace`, route to the domain-appropriate service; skip + log when the pump role is unmapped or the entity is unavailable (`__init__.py`)
- [x] 5.3 Unit-test service routing and the unmapped/unavailable skip (`tests/test_init.py` or `tests/test_pump_service.py`)

## 6. i18n and docs

- [x] 6.1 Add `strings.json` + `translations/en.json` labels for the pump roles, power fields, switch/sensor entities, and the `set_pump` service (both files in sync)
- [x] 6.2 Add RDWC-pump help text describing the stop-pump-before-dosing header-bucket workflow
- [x] 6.3 Update `README.md`/`CHANGELOG.md`: pump control + power monitoring under shipped features

## 7. Validation

- [x] 7.1 Full test pass for switch, power, service, and options-flow changes
- [x] 7.2 `ruff check .` clean and `hassfest`/HACS validation pass
- [x] 7.3 Extend `scripts/validate_live_ha.py` to PASS on mapped pumps and report per-pump + total power
- [x] 7.4 Manual live check: map each pump; toggle the dashboard switch and confirm the outlet responds and state mirrors; confirm power sensors read; run the stop-pump → dose → restart workflow on the 4x4 header bucket
