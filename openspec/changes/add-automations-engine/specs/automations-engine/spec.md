## ADDED Requirements

### Requirement: Per-grow-space rules engine
The integration SHALL provide a per-grow-space rules engine that evaluates
operator-configured rules against telemetry, derived metrics, per-space targets and
schedules, and AI health results, and that runs each space independently.

#### Scenario: Rules evaluated per space
- **WHEN** two grow spaces have different rules
- **THEN** each space's engine evaluates only its own rules with its own inputs

#### Scenario: Invalid rule is skipped
- **WHEN** a stored rule fails validation on load
- **THEN** the engine skips it, logs a warning, and continues with valid rules

### Requirement: Rule triggers
A rule SHALL support triggers for a mapped metric outside a target range, VPD
outside a range, a schedule time boundary, an AI severity threshold, an AI score
threshold, and the critical-alert turning on. A trigger referencing an unknown or
unavailable input MUST NOT fire.

#### Scenario: Metric out of range fires
- **WHEN** a mapped pH reading falls outside the rule's configured range
- **THEN** the rule's trigger condition is met

#### Scenario: Unknown input does not fire
- **WHEN** a rule references a sensor whose state is unknown or unavailable
- **THEN** the rule does not fire

### Requirement: Rule actions
A rule SHALL support a notify action and a control action. A control action MUST
target only a **mapped** control role and MUST call the Home Assistant service
appropriate to the resolved entity's domain; an unmapped or unavailable control
MUST be skipped and logged.

#### Scenario: Notify action
- **WHEN** a rule with a notify action fires
- **THEN** the engine sends the configured notification

#### Scenario: Control action on a mapped control
- **WHEN** a rule with a control action fires in acting mode and the role is mapped
- **THEN** the engine calls the correct on/off/toggle service for that entity

#### Scenario: Control action skipped when unmapped
- **WHEN** a control action's role is not mapped
- **THEN** the engine skips the action and logs it, taking no control call

### Requirement: Safety modes and gating
Each grow space SHALL have an automation mode of `off`, `suggest`, or `act`,
defaulting to a non-acting mode, and a manual arm/disarm control that, when
disarmed, forces no actuation regardless of mode. In `suggest` mode the engine MUST
notify and record but MUST NOT actuate controls.

#### Scenario: Suggest mode does not actuate
- **WHEN** a control rule fires while the space is in `suggest` mode
- **THEN** the engine notifies and records the suggested action but performs no control call

#### Scenario: Disarm halts actuation
- **WHEN** the space is disarmed
- **THEN** no rule actuates a control even if the mode is `act`

### Requirement: Cooldowns and active hours
A rule SHALL honor a cooldown so it does not re-fire until the cooldown elapses, and
MAY define active hours outside which it does not fire.

#### Scenario: Cooldown prevents re-fire
- **WHEN** a rule fired less than its cooldown ago
- **THEN** the rule does not fire again until the cooldown elapses

#### Scenario: Outside active hours
- **WHEN** a rule with active hours is evaluated outside that window
- **THEN** the rule does not fire

### Requirement: Observability
The integration SHALL expose a "last automation action" sensor and a
next-scheduled-check sensor per grow space, and SHALL record a logbook or event
entry whenever a rule acts or (in suggest mode) would act.

#### Scenario: Last action is recorded
- **WHEN** a rule fires
- **THEN** the last-automation-action sensor updates with the rule id, action, mode, and result

### Requirement: Automation services
The integration SHALL provide services to run rules immediately, set the automation
mode, and simulate a rule without acting.

#### Scenario: Simulate performs no action
- **WHEN** the `simulate_rule` service is called for a rule
- **THEN** the engine returns the evaluated action plan and performs no control call

#### Scenario: Set mode
- **WHEN** the `set_automation_mode` service sets a space to `act`
- **THEN** subsequent qualifying rules may actuate controls while armed
