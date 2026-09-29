# Design: add-water-safety-monitoring

## Context

This change adds two RDWC safety mechanisms — **flow verification** and **leak
detection with opt-in pump shutoff** — on top of the existing per-space sensor
mapping and the `add-pump-power-control` pump switches. It is partly a hardware
investigation: the grow does not yet have flow or leak sensors installed, so device
selection precedes code.

## Goals / Non-Goals

**Goals**
- Confirm the RDWC pump is actually circulating water, not just powered.
- Detect a leak fast and, optionally, cut the RDWC pump to limit damage.
- Surface clear per-space safety state and alerts.

**Non-Goals**
- No general rules engine (that is `add-automations-engine`).
- No automatic pump *start*; shutoff only ever turns the RDWC pump **off**.
- No cloud dependency; all logic runs locally in Home Assistant.

## Hardware investigation (precedes code)

- **Flow sensing** options to evaluate:
  - Inline **flow switch** (boolean: flow / no-flow) — simplest, cheapest, robust.
  - Hall-effect **flow meter** (e.g. YF-S201 class) read via an ESPHome node exposing
    a pulse/rate sensor to HA, or a Zigbee/Zigbee2MQTT flow device.
  - Consider placement on the return line so a clog upstream still shows as no-flow.
- **Leak detection** options:
  - Zigbee water/leak sensors (spot or rope-probe) placed at the tent floor, under the
    reservoir, and near fittings; support **multiple** per space.
- Deliverable: a short recommended-hardware note (device, interface, HA entity type,
  placement) added to `README.md` before implementation tasks begin.

## Roles and config (`const.py`, options flow)

- `SENSOR_ROLE_WATER_FLOW = "water_flow"` — either a numeric flow rate (L/min) or a
  boolean flow switch; the monitor treats `> 0` / `on` as "flowing".
- `SENSOR_ROLE_LEAK = "leak"` — mapped to one or more leak entities (support a list).
- `CONF_LEAK_SHUTOFF_ENABLED` (bool, default **False**) — opt-in RDWC-pump shutoff.
- Debounce keys: `CONF_NO_FLOW_GRACE_SECONDS` (default ~60s, allow pump spin-up),
  `CONF_LEAK_DEBOUNCE_SECONDS` (default ~5s).
- Mapped in the same options flow as other roles; leak accepts multiple entities.

## Water-safety monitor

- Subscribe to the mapped flow entity, all mapped leak entities, and the RDWC pump
  switch state.
- **Flow verification**: when the RDWC pump is on for longer than the no-flow grace
  period but flow reads not-flowing, set `flow_ok = off` and raise a no-flow alert;
  clear when flow resumes or the pump is off. No-flow is **alert-only** by default.
- **Leak handling**: when any leak entity turns on (debounced), set
  `leak_detected = on`, raise a **critical** alert, notify, and — only if
  `CONF_LEAK_SHUTOFF_ENABLED` and the RDWC pump is mapped — call the pump-control
  path to turn the RDWC pump **off**; log the action. Never auto-restart the pump.
- Expose `sensor.<grow>_water_safety_status` with states `ok` / `no_flow` / `leak`
  (leak takes priority), plus attributes (which leak entity, last transition time).
- Record a logbook/event entry on every transition.

## Entities

- `binary_sensor.<grow>_flow_ok` (device_class `problem` inverted, or `moisture`/
  `running` as appropriate).
- `binary_sensor.<grow>_leak_detected` (device_class `moisture`).
- `sensor.<grow>_water_safety_status` (enum: ok / no_flow / leak).

## Safety

- Shutoff defaults **off**, only turns the pump **off**, requires the RDWC pump to be
  mapped, is debounced, and is fully logged. If the pump is unmapped, leak handling
  degrades to alert-only.
- No-flow defaults to alert-only to avoid nuisance shutoffs during priming/spin-up.
- All thresholds/debounces are configurable per space.

## Testing strategy

- Flow verification: pump on + no flow past grace → no-flow alert; flow present → ok;
  pump off → no no-flow alert.
- Leak: leak on (debounced) → critical alert + `leak_detected`; with shutoff enabled
  and pump mapped → RDWC pump commanded off exactly once and logged; with shutoff
  disabled or pump unmapped → alert-only, no command.
- Status precedence: leak overrides no-flow in `water_safety_status`.
- Multiple leak entities: any one tripping raises the alert.

## Open questions

- Preferred flow hardware (boolean switch vs. metered rate) — pick during research.
- Whether to add an optional auto-restart-after-clear for no-flow (default: no).
- Whether leak shutoff should also cut the chiller/air pumps or only the RDWC pump
  (default: RDWC only).
