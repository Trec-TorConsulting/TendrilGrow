## Context

`STAGE_TARGETS` holds pH, EC, and VPD bands per stage and the AI prompt quotes them. Nothing compares live sensor state to those bands between vision checks. Water readings on this setup come from the bound LocalTuya device's entities. This change only reads those entity states. It does not poll Tuya cloud, does not change datapoint scaling, and does not read or write `local_key`.

Actuation belongs to `add-automations-engine`. This change notifies only.

## Goals / Non-Goals

**Goals:**

- Problem binary sensors for pH, EC, and VPD, plus one summary.
- Notify on the transition into a breach, with a per-metric cooldown.
- Operator target entities from `add-grow-targets` override the stage table when present. Until that change lands, use `STAGE_TARGETS` for the current stage.

**Non-Goals:**

- Turning pumps, lights, or fans on or off.
- Cloud Tuya polling or conductivity math.
- Alerts for metrics with no mapping or no band (harvest, dry, cure, ready have no reservoir band).

## Decisions

### Edge-triggered notify

Subscribe to the mapped pH, EC, and the derived VPD sensor. A metric is out of range when a numeric state is strictly below the low bound or strictly above the high bound. Notify when the metric enters the out-of-range state, not on every update while it stays out. Cooldown default is 6 hours per metric, stored on the entry options. Clearing back into range resets the edge so the next breach notifies again after the cooldown has elapsed.

### Bounds

If `add-grow-targets` entities exist and have values, use them. Otherwise parse `STAGE_TARGETS[stage]`. If the stage has no band, that metric's binary sensor is off and not a problem. Unavailable source → binary sensor unavailable, no notify.

### Notify service

Reuse `ai_notify_service` when set. Always fire a Home Assistant notification event as well so the alert is visible without a notify service. Do not create a second notify configuration in this change.

### No actuation

The monitor has no reference to pump or light services.

## Risks / Trade-offs

- [Noisy pH probe chatters around the limit] → Cooldown plus edge trigger. A future hysteresis can wait.
- [Targets change lands later] → Band code reads optional target entity ids and falls back to the stage table, so either order of implementation works.

## Migration Plan

New entities only. No migration of existing entries. Default is enabled once the source sensor exists; there is no cloud credential involved.

## Open Questions

None.
