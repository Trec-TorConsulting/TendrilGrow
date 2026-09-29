# Tasks: add-water-safety-monitoring

> Forward-looking + **research** change — **not yet implemented**. Depends on
> `add-pump-power-control` for the RDWC-pump shutoff. Section 1 is a hardware
> investigation that precedes code. Do not check a box until its verification passes.

## 1. Hardware research (precedes code)

- [x] 1.1 Evaluate flow-sensing options (inline flow switch vs. hall-effect flow meter via ESPHome vs. Zigbee flow device); pick one and note interface + HA entity type
- [x] 1.2 Evaluate Zigbee leak sensors for in-tent placement (spot vs. rope probe); confirm multiple-per-space support
- [x] 1.3 Document recommended hardware, wiring, and placement in `README.md` (return-line flow sensing; leak sensors at floor/reservoir/fittings)
- [x] 1.4 Confirm the chosen devices expose usable HA entities (boolean/rate for flow; `moisture` binary_sensor for leak)

## 2. Roles, constants, and config

- [x] 2.1 Add `SENSOR_ROLE_WATER_FLOW` and `SENSOR_ROLE_LEAK` (multi-entity) and `CONF_LEAK_SHUTOFF_ENABLED` (default False) plus debounce keys (`const.py`)
- [x] 2.2 Add options-flow fields: map a flow entity, map one or more leak entities, toggle leak-shutoff, set no-flow grace and leak debounce (`config_flow.py`)
- [x] 2.3 Unit-test that flow/leak mappings and the shutoff/debounce settings persist and reload (`tests/test_config_flow.py`)

## 3. Water-safety monitor

- [x] 3.1 Implement a monitor that subscribes to the flow entity, all leak entities, and the RDWC pump switch state
- [x] 3.2 Implement flow verification: pump on beyond the grace period with no flow → no-flow condition; clears on flow or pump-off (alert-only by default)
- [x] 3.3 Implement leak handling: any leak entity on (debounced) → critical alert + notify
- [x] 3.4 Wire monitor start/stop into `async_setup_entry`/`async_unload_entry`

## 4. Opt-in RDWC pump shutoff

- [x] 4.1 On leak, if `CONF_LEAK_SHUTOFF_ENABLED` and the RDWC pump is mapped, command the pump **off** via the pump-power-control path exactly once; log it
- [x] 4.2 Never auto-restart the pump; require manual re-enable after a leak
- [x] 4.3 Degrade to alert-only when shutoff is disabled or the pump is unmapped
- [x] 4.4 Unit-test: shutoff fires once when enabled+mapped; no command when disabled or unmapped; debounce prevents transient trips

## 5. Safety entities and observability

- [x] 5.1 Add `binary_sensor.<grow>_flow_ok` and `binary_sensor.<grow>_leak_detected`
- [x] 5.2 Add `sensor.<grow>_water_safety_status` (ok / no_flow / leak; leak takes priority) with transition attributes
- [x] 5.3 Record a logbook/event entry on every safety-state transition
- [x] 5.4 Add `strings.json`/`translations/en.json` labels for the new fields and entities

## 6. Validation

- [x] 6.1 Full test pass for flow verification, leak handling, shutoff gating, and status precedence
- [x] 6.2 `ruff check .` clean and `hassfest`/HACS validation pass
- [x] 6.3 Extend `scripts/validate_live_ha.py` to report flow/leak mappings and water-safety status when present
- [x] 6.4 Manual live check (after hardware install): simulate no-flow (pump on, line closed) → alert; trip a leak sensor → critical alert and, with shutoff enabled, RDWC pump turns off
