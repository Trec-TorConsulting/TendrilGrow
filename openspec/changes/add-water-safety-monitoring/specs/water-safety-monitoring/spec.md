## ADDED Requirements

### Requirement: Water-flow verification
The integration SHALL verify RDWC circulation by reconciling the commanded RDWC-pump
state with an observed flow signal, and SHALL raise a no-flow alert when the pump has
been on beyond a configurable grace period but no flow is detected. The no-flow
condition MUST clear when flow resumes or the pump is off, and MUST default to
alert-only (no actuation).

#### Scenario: No flow while pump is on
- **WHEN** the RDWC pump is on past the grace period and the flow sensor reads not-flowing
- **THEN** the integration raises a no-flow alert and reports flow not OK

#### Scenario: Flow present
- **WHEN** the RDWC pump is on and flow is detected
- **THEN** the integration reports flow OK and raises no alert

#### Scenario: Pump off is not a fault
- **WHEN** the RDWC pump is off and no flow is detected
- **THEN** the integration does not raise a no-flow alert

### Requirement: Leak detection
The integration SHALL support mapping one or more leak/water-detector entities per
grow space and SHALL, when any mapped leak entity reports wet (after a short
debounce), set a leak-detected state, raise a critical alert, and notify. Multiple
leak entities MUST be supported, any one of which can trigger.

#### Scenario: Leak triggers a critical alert
- **WHEN** a mapped leak sensor reports wet beyond the debounce window
- **THEN** the integration sets leak-detected, raises a critical alert, and notifies

#### Scenario: Any of several leak sensors triggers
- **WHEN** a grow space maps three leak sensors and one reports wet
- **THEN** the integration treats the space as leaking

#### Scenario: Transient blip is debounced
- **WHEN** a leak sensor reports wet only briefly, shorter than the debounce window
- **THEN** the integration does not raise a leak alert

### Requirement: Opt-in RDWC pump shutoff on leak
The integration SHALL provide an opt-in setting, defaulting to off, that on a leak
commands the mapped RDWC pump off. When enabled and the RDWC pump is mapped, the
shutoff MUST turn the pump off exactly once per leak event, MUST NOT automatically
restart it, and MUST be logged. When disabled or the pump is unmapped, leak handling
MUST degrade to alert-only.

#### Scenario: Shutoff enabled and pump mapped
- **WHEN** a leak is detected, shutoff is enabled, and the RDWC pump is mapped
- **THEN** the integration commands the RDWC pump off once and logs the action

#### Scenario: Shutoff disabled
- **WHEN** a leak is detected and shutoff is disabled
- **THEN** the integration alerts and notifies but issues no pump command

#### Scenario: No automatic restart
- **WHEN** the RDWC pump was shut off by a leak event
- **THEN** the integration does not turn the pump back on automatically

### Requirement: Water-safety status and entities
The integration SHALL expose per-grow-space safety entities — a flow-OK indicator, a
leak-detected indicator, and a water-safety status of ok, no-flow, or leak with leak
taking priority — and SHALL record an event on every safety-state transition.

#### Scenario: Status reflects a leak first
- **WHEN** a space has both no flow and a leak
- **THEN** the water-safety status reports leak

#### Scenario: Transition is recorded
- **WHEN** the water-safety status changes
- **THEN** the integration records a logbook/event entry for the transition
