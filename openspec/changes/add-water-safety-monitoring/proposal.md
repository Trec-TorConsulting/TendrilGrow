# Proposal: add-water-safety-monitoring

> Status: **research + forward-looking**. Captures two operator-raised safety needs.
> Some tasks are hardware investigations that precede implementation.

## Why

RDWC failures are high-consequence and fast. Two gaps stand out:

1. **No proof the pumps are actually moving water.** A pump outlet can be "on" (and
   even drawing power) while flow has stopped — a clog, an air-lock, a failed
   impeller, or a kinked line. Roots then lose circulation and dissolved oxygen
   within hours. Knowing a switch is on is not the same as knowing water is flowing.
2. **No fast leak detection or response.** A split fitting, an overflowing bucket, or
   a burst line can drain the reservoir or flood the tent. The sooner a leak is
   detected and the **RDWC pump is shut off**, the less water is lost and the lower
   the electrical/mold risk.

The operator wants TendrilGrow to (a) verify circulation via a **flow sensor** and
alert when a pump is commanded on but no flow is seen, and (b) ingest **water/leak
detectors** placed inside each tent and, on a leak, raise a critical alert and
optionally cut the RDWC pump. This builds directly on `add-pump-power-control`, which
provides the pump on/off control used for shutoff.

## What Changes

- **Research**: identify suitable flow-sensing hardware (inline flow switch or flow
  meter; hall-effect meters such as the YF-S201 class via an ESPHome/Zigbee bridge,
  or a Zigbee/Zigbee2MQTT flow device) and Zigbee **leak sensors** for in-tent
  placement; document recommended, HA-compatible devices and wiring.
- Add per-space sensor roles: `water_flow` (flow rate or a boolean flow switch) and
  one or more `leak` detectors (support multiple leak entities per space).
- Add **flow verification**: reconcile commanded RDWC-pump state with observed flow;
  when the pump is on but no flow is detected for a debounce window, raise a
  "no-flow" alert (and expose a `flow_ok` binary sensor).
- Add **leak response**: expose a `leak_detected` binary sensor per space; on leak,
  raise a critical alert, notify, and — **opt-in** — command the RDWC pump OFF via the
  pump-power-control switch, with the action gated, debounced, and logged.
- Add per-space **water-safety status** (ok / no-flow / leak) and logbook/event
  entries on every transition.

## Capabilities

### New Capabilities
- `water-safety-monitoring`: Flow verification and leak detection for RDWC spaces,
  with safety entities and an opt-in, guarded RDWC-pump shutoff on leak.

### Modified Capabilities
<!-- None. Consumes existing sensor mapping and the pump control from
add-pump-power-control; no existing requirement changes. -->

## Impact

- **Depends on**: `add-pump-power-control` (the RDWC pump switch used for shutoff).
- **New code**: flow/leak sensor roles and mapping fields; a `water_safety` monitor
  that subscribes to flow/leak/pump state; `flow_ok`/`leak_detected` binary sensors;
  a `water_safety_status` sensor; opt-in shutoff wiring; `services.yaml` +
  `strings.json`/`translations` labels.
- **Constants**: `SENSOR_ROLE_WATER_FLOW`, `SENSOR_ROLE_LEAK` (multi), a
  `CONF_LEAK_SHUTOFF_ENABLED` opt-in flag, and no-flow/leak debounce keys.
- **Safety**: shutoff is opt-in and defaults **off**; it only ever turns the RDWC
  pump **off** (never on), is debounced to avoid transient trips, requires the pump to
  be mapped, and logs every action. No-flow handling defaults to alert-only.
- **Hardware**: flow sensing and leak detection require additional devices; the
  research tasks precede the code tasks.
- **No breaking changes**: additive and disabled until flow/leak sensors are mapped.
