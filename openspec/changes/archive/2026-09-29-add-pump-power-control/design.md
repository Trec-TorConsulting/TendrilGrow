# Design: add-pump-power-control

## Context

RDWC circulation, water-chiller, and air pumps are each powered by a Zigbee-switched
outlet already exposed in Home Assistant as a `switch` (or `input_boolean`) entity.
TendrilGrow maps sensors and controls per grow space via a role → entity-id
dictionary (`GrowSpace.control_mappings`) that is edited in the options flow (the
same form that maps the camera, lights, fans, and inline fans) and merged from
`entry.data` + `entry.options` at setup. This change adds pump roles, proxy switch
entities, power monitoring, and a control service, reusing that existing plumbing.

## Goals / Non-Goals

**Goals**
- Map three pump roles per space and expose grouped on/off switch entities.
- Show per-pump power draw and a per-space total, with minimal user configuration.
- Provide a service for scripts/automations to actuate pumps safely.

**Non-Goals**
- No automatic/rule-based actuation (that is `add-automations-engine`).
- No flow verification or leak response (that is `add-water-safety-monitoring`).
- No new hardware integration; consumes existing HA `switch`/`sensor` entities.

## Roles and constants (`const.py`)

```python
CONTROL_ROLE_RDWC_PUMP = "rdwc_pump"
CONTROL_ROLE_CHILLER_PUMP = "chiller_pump"
CONTROL_ROLE_AIR_PUMP = "air_pump"

PUMP_CONTROL_ROLES: tuple[str, ...] = (
    CONTROL_ROLE_RDWC_PUMP,
    CONTROL_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_AIR_PUMP,
)

# Existing CONTROL_ROLES gains the three pump roles (appended, order preserved).
CONTROL_ROLES = (
    CONTROL_ROLE_LIGHTS,
    CONTROL_ROLE_FANS,
    CONTROL_ROLE_INLINE_FANS,
    CONTROL_ROLE_RDWC_PUMP,
    CONTROL_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_AIR_PUMP,
)

# Optional explicit power-sensor roles (stored under sensor_mappings).
POWER_SENSOR_ROLE_RDWC_PUMP = "rdwc_pump_power"
POWER_SENSOR_ROLE_CHILLER_PUMP = "chiller_pump_power"
POWER_SENSOR_ROLE_AIR_PUMP = "air_pump_power"

PUMP_POWER_ROLE_FOR: dict[str, str] = {
    CONTROL_ROLE_RDWC_PUMP: POWER_SENSOR_ROLE_RDWC_PUMP,
    CONTROL_ROLE_CHILLER_PUMP: POWER_SENSOR_ROLE_CHILLER_PUMP,
    CONTROL_ROLE_AIR_PUMP: POWER_SENSOR_ROLE_AIR_PUMP,
}

PUMP_LABELS: dict[str, str] = {
    CONTROL_ROLE_RDWC_PUMP: "RDWC Pump",
    CONTROL_ROLE_CHILLER_PUMP: "Water Chiller Pump",
    CONTROL_ROLE_AIR_PUMP: "Air Pump",
}
```

Adding the pump roles to `CONTROL_ROLES` makes them appear automatically in the
options flow's control-mapping loop and makes them addressable by the automations
engine's control action later.

## Options flow

- Pump roles are shown in the existing control-mapping section. Use a domain-limited
  selector for pumps so users pick the right entity:
  `EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))`.
  Lights/fans keep their current generic selector.
- Power sensors are **optional**. Provide one optional `sensor`-domain field per pump
  (`device_class: power` filter where supported). If left blank, power is
  auto-discovered (below). Store non-empty power mappings under `sensor_mappings`
  using the `*_power` role keys, so they flow through the existing merge and
  `GrowSpace.from_dict` unchanged.

## Proxy switch platform (`switch.py`)

Add `switch` to `PLATFORMS`. For each **mapped** pump role, create one entity:

- `unique_id = f"{space_id}_{role}"` (e.g. `..._rdwc_pump`).
- `name = PUMP_LABELS[role]`; attach to the grow-space `DeviceInfo` (shared identifier
  with the space's other entities) so it groups on the device page and dashboards.
- `is_on`: read the mapped entity's state; `True` when `state == "on"`.
- `available`: `False` when the mapped entity is missing or `unavailable`/`unknown`.
- `async_turn_on` / `async_turn_off` / `async_toggle`: resolve the mapped entity's
  domain and call the matching service — `switch.turn_on/off`, `input_boolean.turn_on/off`,
  else `homeassistant.turn_on/off` as a generic fallback — with the mapped entity id.
- Subscribe with `async_track_state_change_event` to the mapped entity and call
  `async_write_ha_state` on change so the proxy mirrors promptly.
- Do not create a switch for an unmapped role; on options change, reload adds/removes.

Coordination: if `add-automations-engine` has already created `switch.py` (arm/disarm
switch), add the pump entities alongside it in the same `async_setup_entry` platform
function rather than creating a second module.

## Power monitoring (`sensor.py` or `power.py`)

Resolve a power source per mapped pump:

1. If `sensor_mappings[<role>_power]` is set, use it.
2. Else auto-discover: find the pump switch entity's `device_id` via the entity
   registry, then pick a sensor entity on the same device whose `device_class` is
   `power` (prefer unit `W`); if only `energy` (`kWh`) exists, use it for an energy
   sensor only. Ignore if none found.

Entities:
- Per pump with a resolved power source: `sensor.<grow>_<role>_power`
  (`device_class: power`, unit `W`), mirroring the source value; `unavailable` when
  the source is unavailable.
- Per space: `sensor.<grow>_total_pump_power` = sum of currently-available pump power
  values (numeric), `0` when none are on, `unavailable` only when no source exists.
- Energy is optional; if a source energy sensor is found, expose
  `sensor.<grow>_<role>_energy` (`device_class: energy`, `kWh`,
  `state_class: total_increasing`). Keep MVP focused on power (W) + total.

## `set_pump` service (`__init__.py`, `services.yaml`)

- Name: `tendrilgrow.set_pump`. Fields:
  - `entry_id` (string, required) — target grow-space config entry.
  - `pump` (select: `rdwc_pump` | `chiller_pump` | `air_pump`, required).
  - `action` (select: `on` | `off` | `toggle`, required).
- Behavior: resolve the entry's runtime `GrowSpace`, look up the mapped control
  entity for `pump`; if unmapped or unavailable, log a warning and return without
  error; otherwise call the domain-appropriate service (same routing as the switch).
- This is the automation/script entry point and mirrors the proxy switch behavior.

## Safety and UX

- Manual only: no state is changed except by explicit switch/service/automation calls.
- The RDWC pump switch is the one used in the dosing workflow; its entity name and
  `strings.json` help text should mention "turn OFF before dosing the header bucket,
  then back ON after mixing."
- Power draw is a coarse running indicator only; true flow verification is deferred to
  `add-water-safety-monitoring`.

## Testing strategy

- Switch state mirroring: underlying on/off → proxy `is_on`; underlying unavailable →
  proxy unavailable.
- Service/turn routing by domain (`switch`, `input_boolean`, generic fallback).
- Unmapped/unavailable pump: switch not created / service skips and logs.
- Power source resolution: explicit mapping used; auto-discovery from device works;
  total equals the sum of available per-pump values.
- Options flow persists pump control mappings and optional power mappings; reload
  adds/removes proxy entities.

## Migration

None. All additions are optional and appear only when a pump role is mapped; existing
config entries load unchanged.
