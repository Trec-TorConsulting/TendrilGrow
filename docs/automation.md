# Automating TendrilGrow

TendrilGrow exposes services and entities you can use in your own Home Assistant
automations, scripts, and dashboards. Control is **manual and opt-in** — you
decide what to automate, and you are responsible for validating it.

!!! warning "Safety"
    Automating pumps and other hardware carries real electrical and water risk.
    Test thoroughly, add your own guardrails, and never rely on this as a safety
    system.

## Building blocks available today

### Services

- `tendrilgrow.run_ai_health_check`
- `tendrilgrow.rebuild_automap`
- `tendrilgrow.set_pump`
- `tendrilgrow.mark_flush`
- `tendrilgrow.capture_timelapse_frame`
- `tendrilgrow.build_timelapse`

See [Services](services.md) for fields and examples.

### Trigger-friendly entities

- **Flush Due** (binary sensor, problem) — on when a reservoir flush is overdue.
- **AI Health Critical Alert** (binary sensor) — on when the latest AI score is
  at or below your threshold.
- **VPD**, **Dew Point**, **DLI** (sensors) — for climate and light automations.
- **Grow Timeline** (calendar) — trigger on projected stage, harvest, and flush
  dates.

## Examples

Entity IDs below are examples — adjust them to your own grow spaces.

### Actionable flush reminder (mobile app)

Notify with a button that records the flush when tapped.

```yaml
automation:
  - alias: "Grow: flush overdue reminder"
    triggers:
      - trigger: state
        entity_id: binary_sensor.3x3_mothers_tent_flush_due
        to: "on"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "Reservoir flush due"
          message: "The 3x3 tent reservoir is overdue for a flush."
          data:
            actions:
              - action: "TG_MARK_FLUSH"
                title: "Mark flushed"

  - alias: "Grow: handle flush action"
    triggers:
      - trigger: event
        event_type: mobile_app_notification_action
        event_data:
          action: "TG_MARK_FLUSH"
    actions:
      - action: tendrilgrow.mark_flush
        data:
          entry_id: 0123456789abcdef0123456789abcdef
```

### VPD-driven exhaust

```yaml
automation:
  - alias: "Grow: exhaust when VPD is high"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.3x3_mothers_tent_vpd
        above: 1.4
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.3x3_inline_fan
```

### Circulate before dosing (RDWC)

```yaml
script:
  grow_dose_prep:
    sequence:
      - action: tendrilgrow.set_pump
        data:
          entry_id: 0123456789abcdef0123456789abcdef
          pump: rdwc_pump
          action: "on"
      - delay: "00:05:00"
      # ... perform your dose while circulating ...
```

### Critical AI score alert with a snapshot

```yaml
automation:
  - alias: "Grow: AI critical alert"
    triggers:
      - trigger: state
        entity_id: binary_sensor.3x3_mothers_tent_ai_health_critical_alert
        to: "on"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "Grow health critical"
          message: "{{ states('sensor.3x3_mothers_tent_ai_health_summary') }}"
```

## Roadmap: first-class automation support

The following are planned and tracked in the OpenSpec backlog rather than
implemented today:

- A safety-first, opt-in **automation engine** with guardrails (water
  temperature, pH/EC bounds) — see the `add-automations-engine` change.
- **Event bus events** (for example `tendrilgrow_flush_recorded`,
  `tendrilgrow_ai_check_completed`) for simpler triggering.
- Bundled **automation blueprints** (VPD control, flush reminders).
- Pursuing the Home Assistant **integration quality scale**.

Track progress in
[openspec/changes](https://github.com/Trec-TorConsulting/TendrilGrow/tree/main/openspec/changes).
