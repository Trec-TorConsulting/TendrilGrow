# Design: add-automations-engine

## Context

The model already stores control-role mappings, targets, and schedules, and the AI
health runtime emits scored results. This change adds a rules engine that turns
those inputs into actions. Because actions can drive real hardware (pumps, lights,
fans), the design is **safety-first**: notify-only by default, opt-in actuation,
only on mapped controls, rate-limited, and fully logged. A cheaper implementation
model should follow the ordered tasks and the schemas below.

Constraints:
- Async-only; per grow-space config entry (spaces isolated).
- Never actuate an unmapped control or act on unknown/unavailable inputs.
- Deterministic, testable evaluation; no external dependencies.

## Data model

Per-entry automation config (stored in entry options):
```python
CONF_AUTOMATION_MODE = "automation_mode"  # "off" | "suggest" | "act"
CONF_RULES = "automation_rules"  # list[Rule]
```
Rule (a plain dict persisted in options; validated on load):
```python
{
    "id": "vpd_high",  # stable slug, unique per space
    "enabled": true,
    "trigger": {
        "type": "metric_range"
        | "vpd_range"
        | "schedule"
        | "ai_severity"
        | "ai_score"
        | "critical_alert",
        # metric_range: {"role": "ph", "min": 5.6, "max": 6.2}
        # vpd_range:    {"min": 0.8, "max": 1.5}
        # schedule:     {"on": "06:00", "off": "00:00"}  # lights-style window
        # ai_severity:  {"at_least": "high"}             # low<medium<high<critical
        # ai_score:     {"at_most": 40}
        # critical_alert: {}
    },
    "action": {
        "type": "notify" | "control",
        # notify:  {"service": "notify.mobile_app_x", "message": "..."}  (service optional)
        # control: {"role": "lights", "command": "on"|"off"|"toggle"}
    },
    "cooldown_minutes": 30,
    "active_hours": {"start": "00:00", "end": "23:59"},  # optional
}
```

## Evaluation flow

1. On setup, build an `AutomationEngine(hass, entry, grow_space)` and load rules.
2. Subscribe to inputs:
   - `async_track_state_change_event` for each mapped sensor entity id.
   - the AI dispatcher signal (`ai_dispatcher_signal(entry_id)`).
   - `async_track_time_interval` (e.g., 1 min) for schedule/active-hours checks.
3. On any trigger, `evaluate()` iterates enabled rules; a rule fires when its
   trigger condition is met, it is inside `active_hours`, and its `cooldown` has
   elapsed since `last_fired`.
4. Firing produces an `ActionPlan`. The engine's behavior depends on **mode**:
   - `off`: do nothing.
   - `suggest`: record the plan, emit a logbook/event entry, send a notification
     describing the suggested action, but do NOT actuate controls.
   - `act`: for `notify` actions, notify; for `control` actions, resolve the mapped
     control entity and call the correct HA service by domain
     (`light`/`switch`/`fan`), then record and log.
5. Update `last_fired`, the "last automation action" sensor, and the
   next-scheduled-action sensor.

## Actuation safety

- **Only mapped controls**: a `control` action resolves `grow_space.control_mappings[role]`;
  if unmapped or the entity is unavailable, the action is skipped and logged.
- **Domain-correct service**: derive service from the entity domain
  (`light.turn_on/off/toggle`, `switch.turn_on/off/toggle`, `fan.turn_on/off/toggle`).
- **Manual arm/disarm**: a per-space `switch.<grow>_automations_armed`; when off,
  the engine forces `off` regardless of configured mode.
- **Cooldown + active-hours** prevent oscillation and off-hours actions.
- **Dry-run**: `simulate_rule` evaluates a rule and returns the plan without acting.
- **Unknown inputs**: rules referencing unknown/unavailable states are skipped, not
  fired.

## Entities and services

- `switch.<grow>_automations_armed` (arm/disarm; default off).
- `sensor.<grow>_last_automation_action` (state = short description; attributes:
  rule id, action, mode, result, timestamp).
- `sensor.<grow>_next_automation_check` (timestamp).
- Services (in `services.yaml`): `run_rules_now` (entry_id?),
  `set_automation_mode` (entry_id, mode), `simulate_rule` (entry_id, rule_id).

## Options-flow configuration

Add an "Automations" section to the options flow: select `automation_mode`, and
add/edit/remove rules. For a first version, rules may be entered as a small set of
guided sub-forms (trigger type → fields, action type → fields, cooldown,
active-hours). Persist to `CONF_RULES` in options; reload the entry on save.

## Default rule templates (ship disabled)

- `vpd_high`: trigger `vpd_range` {max: 1.5} → action `notify`.
- `ph_out_of_range`: trigger `metric_range` {role: ph, min: 5.6, max: 6.2} → `notify`.
- `lights_schedule`: trigger `schedule` {on, off} → action `control` {role: lights}.
- `ai_critical`: trigger `critical_alert` → action `notify`.

## Goals / Non-Goals

**Goals:** deterministic, safe, observable per-space automation over existing model
data; opt-in actuation; clear operator control.

**Non-Goals:** a general HA automation replacement, cross-space rules, PID/closed-
loop dosing control, or ML-driven control (future work).

## Risks / Trade-offs

- **Actuating real hardware** → default `suggest` mode, arm/disarm switch,
  mapped-only actuation, cooldowns, active-hours, full logging, dry-run.
- **Rule misconfiguration** → validate rules on load; skip invalid rules with a
  logged warning; `simulate_rule` for safe testing.
- **State-change storms** → debounce evaluation and honor cooldowns.
- **Schedule/timezone** → use HA local time helpers; test around midnight windows.

## Acceptance criteria

- With mode `suggest`, an out-of-range metric produces a notification and a
  logbook entry but no control call.
- With mode `act` and a mapped light, a `lights_schedule` rule turns the light on
  at the configured time and off at the boundary, respecting cooldown.
- Disarming the space stops all actuation immediately.
- Rules referencing unmapped controls or unknown states never actuate.
- `simulate_rule` returns a plan and performs no action.
- Unit tests cover each trigger type, cooldown, active-hours, mapped-only guard,
  and mode gating.

## Migration Plan

Additive and disabled by default (mode `off`/disarmed, no rules). Existing installs
are unaffected until the user configures rules and arms the engine. Rollback:
remove rules / set mode `off`; no external state.
