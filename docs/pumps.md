# Pump control and monitoring

TendrilGrow can control and monitor reservoir pumps — the RDWC circulation pump,
a chiller pump, and an air pump.

## Pump roles

| Role | Description |
| --- | --- |
| `rdwc_pump` | RDWC circulation pump. Run it before any header-bucket dosing. |
| `chiller_pump` | Chiller pump (optional). |
| `air_pump` | Air pump (optional). |

Map each pump to a switchable Home Assistant entity in the **Map entities** step.
A TendrilGrow switch is created for every mapped pump.

## Power monitoring

For each pump you can either:

- Map an explicit power sensor (`rdwc_pump_power`, `chiller_pump_power`,
  `air_pump_power`), or
- Let TendrilGrow discover a power sensor automatically from the device
  registry.

A per-pump **Power** sensor and a **Total Pump Power** sensor report real-time
consumption.

## Controlling pumps

Toggle pumps from the dashboard switches, or from automations and scripts with
[`tendrilgrow.set_pump`](services.md#tendrilgrowset_pump):

```yaml
action: tendrilgrow.set_pump
data:
  entry_id: 0123456789abcdef0123456789abcdef
  pump: rdwc_pump
  action: toggle
```

## RDWC dosing workflow

In a recirculating deep water culture system, the circulation pump should be
running before nutrients are dosed into a header bucket so they mix evenly. Map
the `rdwc_pump` and switch it on before dosing.

!!! warning "Manual and opt-in"
    Pump control is manual and opt-in. TendrilGrow does not automate pump
    actuation for you — you build any automations yourself and are responsible
    for validating them. Always confirm safe electrical and water practices.
