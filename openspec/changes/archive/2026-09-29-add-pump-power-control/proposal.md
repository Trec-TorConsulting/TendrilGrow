# Proposal: add-pump-power-control

## Why

In an RDWC system the reservoir/header bucket feeds every plant bucket in series.
When the operator doses the header bucket for a pH or nutrient correction while the
circulation pump is running, the concentrated dose is pushed straight into the
first inline bucket before it mixes — spiking that plant and risking damage. The
safe procedure is to **stop the RDWC pump, dose and mix the header bucket, then
restart the pump**. The pumps (RDWC circulation pump, water chiller pump, air pump)
are each on their own Zigbee-switched outlet, but TendrilGrow cannot control them
or show their power draw today.

Growers want simple, per-grow-space **on/off switches on the dashboard** for each
pump, mapped the same way cameras and lights are mapped, plus **power-usage
visibility** to confirm a pump is actually drawing current (a first, coarse signal
that it is running). This is a **new, not-yet-built** capability.

## What Changes

- Add three per-grow-space **control roles** — `rdwc_pump`, `chiller_pump`,
  `air_pump` — mappable to a Home Assistant `switch`/`input_boolean` entity in the
  **same options form** used for camera, lights, fans, and inline fans.
- Add a **`switch` platform**: one proxy switch per mapped pump role per space,
  grouped under that space's device, that forwards on/off/toggle to the mapped
  entity and mirrors its state and availability.
- Add **power monitoring**: for each mapped pump, resolve a power sensor — either an
  optional explicit mapping (`rdwc_pump_power`, `chiller_pump_power`,
  `air_pump_power`) or **auto-discovery** from the pump switch's device — and expose
  a per-pump power sensor plus a per-space **total pump power** sensor.
- Add a **`set_pump` service** (`entry_id`, `pump`, `action` = on/off/toggle) for
  scripts and future automations, which safely skips and logs when a role is
  unmapped or the entity is unavailable.
- Add **i18n labels** for the new roles, switch/sensor entities, and the service.

## Capabilities

### New Capabilities
- `pump-power-control`: Per-grow-space pump on/off switches (RDWC/chiller/air) that
  proxy user-mapped outlet entities, plus per-pump and total power sensors and a
  `set_pump` service — enabling the stop-pump-to-dose header-bucket workflow.

### Modified Capabilities
- `grow-data-model`: The control-role set is extended to explicitly include the
  pump roles `rdwc_pump`, `chiller_pump`, and `air_pump`.

## Impact

- **New code**: `switch.py` (pump proxy switches), pump power sensors in `sensor.py`
  (or `power.py`), power-source resolution/auto-discovery helper, `set_pump` service
  in `__init__.py`, and `services.yaml` entry.
- **Constants**: `CONTROL_ROLE_RDWC_PUMP`, `CONTROL_ROLE_CHILLER_PUMP`,
  `CONTROL_ROLE_AIR_PUMP` added to `CONTROL_ROLES`; a `PUMP_CONTROL_ROLES` subset;
  the `*_power` sensor role constants and a pump→power-role map in `const.py`.
- **Config/UX**: pump roles use a `switch`/`input_boolean`-filtered entity selector
  in the options flow; optional power-sensor mappings; `switch` added to `PLATFORMS`.
- **Coordination**: the `add-automations-engine` change also introduces `switch.py`
  (arm/disarm). Whichever lands first creates the module; the other extends it. Once
  both ship, automations MAY actuate pumps via these mapped controls.
- **Safety**: this change exposes **manual** control and monitoring only; it performs
  no automatic actuation. Turning a pump off/on is always an explicit operator (or
  script/automation) action. Unmapped/unavailable pumps are skipped and logged.
- **No breaking changes**: existing entities and flows are unchanged; all additions
  are optional and appear only when a pump role is mapped.
