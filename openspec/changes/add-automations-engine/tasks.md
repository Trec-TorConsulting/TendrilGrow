# Tasks: add-automations-engine

> Forward-looking change — **not yet implemented**. Work top to bottom; each task
> is independently verifiable. Safety tasks (5) are mandatory before enabling any
> actuation. Do not check a box until its verification passes.

## 1. Config model and constants

- [ ] 1.1 Add constants: `CONF_AUTOMATION_MODE`, `CONF_RULES`, mode enum (`off`/`suggest`/`act`), trigger-type and action-type enums, cooldown/active-hours keys (`const.py`)
- [ ] 1.2 Define a `Rule` validation/normalization helper (`automations/rules.py`) that parses stored dicts, assigns stable ids, and rejects invalid rules with clear reasons
- [ ] 1.3 Unit-test rule parsing: valid rules pass; malformed rules are rejected with reasons (`tests/test_automation_rules.py`)

## 2. Engine core

- [ ] 2.1 Implement `AutomationEngine(hass, entry, grow_space)` (`automations/engine.py`) with `async_start`/`async_stop`, rule storage, and `last_fired` tracking
- [ ] 2.2 Implement `evaluate(trigger_context)` iterating enabled rules and producing `ActionPlan`s
- [ ] 2.3 Implement trigger evaluation for `metric_range`, `vpd_range`, `schedule`, `ai_severity`, `ai_score`, `critical_alert`; skip unknown/unavailable inputs
- [ ] 2.4 Unit-test each trigger type, including the unknown-input skip (`tests/test_automation_engine.py`)

## 3. Inputs and scheduling

- [ ] 3.1 Subscribe to `async_track_state_change_event` for each mapped sensor entity
- [ ] 3.2 Subscribe to the AI dispatcher signal (`ai_dispatcher_signal(entry_id)`)
- [ ] 3.3 Add a 1-minute `async_track_time_interval` for schedule/active-hours checks
- [ ] 3.4 Debounce evaluation so state-change storms do not bypass cooldowns
- [ ] 3.5 Wire engine start/stop into `async_setup_entry`/`async_unload_entry`, per entry

## 4. Actions

- [ ] 4.1 Implement notify action (persistent notification and/or configured notify service) (`automations/actions.py`)
- [ ] 4.2 Implement control action: resolve mapped control entity, derive service from domain (`light`/`switch`/`fan`), call on/off/toggle
- [ ] 4.3 Skip + log control actions when the role is unmapped or the entity is unavailable
- [ ] 4.4 Unit-test control routing by domain and the unmapped/unavailable skip

## 5. Safety (mandatory before actuation)

- [ ] 5.1 Implement mode gating: `off` = no-op; `suggest` = notify+record only; `act` = may actuate
- [ ] 5.2 Add `switch.<grow>_automations_armed` (default off); disarmed forces no actuation
- [ ] 5.3 Enforce per-rule cooldown and optional active-hours before firing
- [ ] 5.4 Implement dry-run path used by `simulate_rule`
- [ ] 5.5 Unit-test: suggest-mode never actuates; disarm halts actuation; cooldown and active-hours gate firing

## 6. Observability

- [ ] 6.1 Add `sensor.<grow>_last_automation_action` (state + rule/action/mode/result/timestamp attributes)
- [ ] 6.2 Add `sensor.<grow>_next_automation_check` (timestamp)
- [ ] 6.3 Record a logbook/event entry whenever a rule acts or would act (suggest)

## 7. Services and options flow

- [ ] 7.1 Register services `run_rules_now`, `set_automation_mode`, `simulate_rule` (`__init__.py`, `services.yaml`)
- [ ] 7.2 Add an "Automations" section to the options flow: set mode; add/edit/remove rules via guided sub-forms; persist to `CONF_RULES`; reload entry on save
- [ ] 7.3 Add `switch` to `PLATFORMS`; add `strings.json`/`translations/en.json` labels for automation fields and services
- [ ] 7.4 Ship the default rule templates (disabled): `vpd_high`, `ph_out_of_range`, `lights_schedule`, `ai_critical`

## 8. Validation

- [ ] 8.1 Full test pass for triggers, actions, safety gating, and services
- [ ] 8.2 Manual check on live HA: suggest mode notifies without acting; act mode drives a mapped light on schedule; disarm stops actuation
- [ ] 8.3 `hassfest`/HACS validation and lint pass
