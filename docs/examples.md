# Examples

Copy-paste starting points. Replace entity IDs with the ones on **your**
TendrilGrow device. Prefixes below assume a grow space named **4x4 Flower**.

Find the config **entry ID** under
**Settings → Devices & Services → TendrilGrow → the entry** (in the URL, or the
visual action picker).

## configuration.yaml — timelapse allow-list

```yaml
homeassistant:
  allowlist_external_dirs:
    - /config/www/tendrilgrow
```

Restart after changing this file. See [Installation](installation.md#allow-list-for-timelapse-optional).

## Lovelace — Cultivation Plan

```yaml
type: entities
title: Cultivation Plan
entities:
  - text.4x4_flower_strain_genetics
  - select.4x4_flower_growth_stage
  - date.4x4_flower_stage_started
  - sensor.4x4_flower_week_in_stage
  - select.4x4_flower_water_type
  - number.4x4_flower_sites_plants
  - number.4x4_flower_total_system_volume
  - number.4x4_flower_target_ph
  - number.4x4_flower_target_ec
  - number.4x4_flower_feed_interval
  - number.4x4_flower_lights_on
  - text.4x4_flower_nutrient_line
  - text.4x4_flower_base_nutrients
  - text.4x4_flower_additives
```

## Lovelace — AI report and feeding

```yaml
type: vertical-stack
cards:
  - type: entities
    title: AI Health
    entities:
      - sensor.4x4_flower_ai_health_score
      - sensor.4x4_flower_ai_health_summary
      - sensor.4x4_flower_ai_last_health_check
      - binary_sensor.4x4_flower_ai_health_critical_alert
      - button.4x4_flower_run_ai_health_check
  - type: markdown
    title: AI Health Report
    content: "{{ state_attr('sensor.4x4_flower_ai_health_score', 'report') }}"
  - type: markdown
    title: AI Feeding Schedule
    content: "{{ state_attr('sensor.4x4_flower_ai_health_score', 'feeding_schedule_md') }}"
```

## Lovelace flush card {#lovelace-flush}

```yaml
type: entities
title: Reservoir Flush
show_header_toggle: false
entities:
  - entity: button.4x4_flower_flush_now
    name: Flush now
    icon: mdi:water-sync
  - entity: number.4x4_flower_flush_interval
    name: Flush interval
  - type: divider
  - entity: binary_sensor.4x4_flower_flush_due
    name: Flush due?
  - entity: sensor.4x4_flower_days_since_flush
  - entity: sensor.4x4_flower_days_until_flush
  - entity: sensor.4x4_flower_next_flush_due
  - entity: sensor.4x4_flower_last_flush
```

## Lovelace — grow timeline

```yaml
type: markdown
title: Grow Timeline
content: |
  **Stage:** {{ states('select.4x4_flower_growth_stage') }}

  **Stage started:** {{ states('date.4x4_flower_stage_started') }}

  **Weeks in stage:** {{ states('sensor.4x4_flower_week_in_stage') }}

  **Days left in stage:** {{ states('sensor.4x4_flower_stage_projection') }} d

  **Projected harvest:** {{ state_attr('sensor.4x4_flower_stage_projection', 'projected_harvest_date') }}
```

## Automation — flush overdue (mobile)

```yaml
automation:
  - alias: "4x4 Flower: flush overdue"
    triggers:
      - trigger: state
        entity_id: binary_sensor.4x4_flower_flush_due
        to: "on"
    actions:
      - action: notify.mobile_app_your_phone
        data:
          title: Reservoir flush due
          message: 4x4 Flower is past the flush interval.
          data:
            actions:
              - action: TG_MARK_FLUSH_4X4
                title: Mark flushed

  - alias: "4x4 Flower: mark flush from notification"
    triggers:
      - trigger: event
        event_type: mobile_app_notification_action
        event_data:
          action: TG_MARK_FLUSH_4X4
    actions:
      - action: tendrilgrow.mark_flush
        data:
          entry_id: REPLACE_WITH_CONFIG_ENTRY_ID
```

## Automation — AI critical

```yaml
automation:
  - alias: "4x4 Flower: AI critical"
    triggers:
      - trigger: state
        entity_id: binary_sensor.4x4_flower_ai_health_critical_alert
        to: "on"
    actions:
      - action: notify.mobile_app_your_phone
        data:
          title: Grow health critical
          message: "{{ states('sensor.4x4_flower_ai_health_summary') }}"
```

## Script: circulate before dosing (RDWC) {#script-circulate-before-dosing-rdwc}

```yaml
script:
  flower_dose_prep:
    alias: Run recirc 5 minutes before dosing
    sequence:
      - action: tendrilgrow.set_pump
        data:
          entry_id: REPLACE_WITH_CONFIG_ENTRY_ID
          pump: rdwc_pump
          action: "on"
      - delay: "00:05:00"
```

## Script — on-demand AI check

```yaml
script:
  flower_ai_check_now:
    sequence:
      - action: tendrilgrow.run_ai_health_check
        data:
          entry_id: REPLACE_WITH_CONFIG_ENTRY_ID
          reason: Manual check after reservoir change
```

## VPD exhaust (you own the fan entity)

```yaml
automation:
  - alias: "4x4 Flower: exhaust when VPD high"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.4x4_flower_vpd
        above: 1.4
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.your_inline_fan
```

!!! warning
    Pump and fan automations are **your** responsibility. Test with yourself
    present. TendrilGrow is not a safety controller.

More context: [Automating TendrilGrow](automation.md).
