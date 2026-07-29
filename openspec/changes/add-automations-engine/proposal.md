# Proposal: add-automations-engine

## Why

TendrilGrow captures targets, light schedules, live telemetry, and AI health
output, but it cannot yet act on them. Growers want the package to close the loop:
warn when VPD/pH/EC drift out of range, follow a light schedule, and respond to
AI-detected problems — safely and transparently. This is a **new, not-yet-built**
capability.

## What Changes

- Add a per-grow-space **rules engine** that evaluates conditions from telemetry,
  derived metrics (VPD), per-space targets/ranges, light schedules, and AI health
  results, then runs actions.
- Add **triggers**: a metric outside its target range, VPD outside range, a
  schedule time boundary, an AI severity/score threshold, and the critical-alert
  binary sensor turning on.
- Add **actions**: send a notification, and (opt-in) actuate a **mapped control**
  (lights/fans/inline fans) via the appropriate Home Assistant service.
- Add a **safety model**: a per-space automation **mode** (`off`, `suggest`,
  `act`), per-rule **cooldowns**, optional **active-hours**, action only on
  **mapped** controls, a **dry-run** path, and a manual **arm/disarm** switch.
- Add **observability**: a "last automation action" sensor, a next-scheduled-action
  sensor, and logbook/event entries for every evaluation that acts or would act.
- Add **services**: `run_rules_now`, `set_automation_mode`, and `simulate_rule`.
- Add **default rule templates** (VPD-high notify, lights on/off by schedule, AI
  critical notify) that ship disabled and are enabled per space.

## Capabilities

### New Capabilities
- `automations-engine`: A safety-first, per-grow-space rules engine — triggers,
  actions (notify + opt-in guarded control actuation), modes/cooldowns/active-hours,
  arm/disarm, observability entities, and control services.

### Modified Capabilities
<!-- None — consumes existing grow-data-model targets/schedules and control roles. -->

## Impact

- **New code**: `automations/engine.py`, `automations/rules.py`,
  `automations/actions.py` (or an `automation_engine.py` module); a per-space
  `switch` (arm/disarm); automation sensors in `sensor.py`; rule configuration in
  the options flow; services + `services.yaml` entries.
- **Constants**: automation config keys (`CONF_AUTOMATION_MODE`, `CONF_RULES`,
  cooldown/active-hours keys) and mode/trigger/action enums in `const.py`.
- **Runtime**: subscribe to mapped-sensor state changes and the AI dispatcher
  signal; schedule time-based rule checks; store per-rule last-fired timestamps.
- **Config/UX**: a new automations section in the options flow to add/edit rules
  and set the mode; `switch` platform added to `PLATFORMS`.
- **Safety**: no action on unmapped controls; default mode is `suggest`
  (notify-only); every action is logged and rate-limited.
- **No breaking changes**: existing entities/flows unchanged; automations are
  additive and disabled by default.
