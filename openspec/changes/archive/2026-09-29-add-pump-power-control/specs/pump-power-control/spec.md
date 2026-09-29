## ADDED Requirements

### Requirement: Pump control roles
The integration SHALL provide three per-grow-space control roles — `rdwc_pump`,
`chiller_pump`, and `air_pump` — each mappable to a Home Assistant `switch` or
`input_boolean` entity in the same options form used for camera, lights, and fan
mappings. An unmapped pump role MUST NOT create any entity.

#### Scenario: Map a pump to an outlet
- **WHEN** the operator maps the `rdwc_pump` role to a Zigbee switch entity
- **THEN** the integration binds that role to the entity and exposes a pump switch for it

#### Scenario: Unmapped pump creates nothing
- **WHEN** a pump role is left unmapped
- **THEN** no switch or power entity is created for that role

### Requirement: Pump on/off switch entities
For each mapped pump role the integration SHALL expose a switch entity, grouped under
that grow space's device, that reflects the mapped entity's on/off state and
availability and that forwards on, off, and toggle commands to the mapped entity using
the service appropriate to the mapped entity's domain. When the mapped entity is
missing or unavailable, the pump switch MUST report unavailable and MUST NOT raise.

#### Scenario: Switch mirrors the outlet
- **WHEN** the mapped outlet turns on
- **THEN** the pump switch reports on

#### Scenario: Command forwards to the outlet
- **WHEN** the operator turns the pump switch off from the dashboard
- **THEN** the integration calls the correct turn-off service for the mapped entity's domain

#### Scenario: Unavailable outlet
- **WHEN** the mapped entity is unavailable or unknown
- **THEN** the pump switch reports unavailable and issues no command

### Requirement: Pump power monitoring
For each mapped pump the integration SHALL resolve a power source — an explicitly
mapped power sensor if provided, otherwise a `power`-class sensor auto-discovered on
the pump switch's device — and, when a source exists, expose a per-pump power sensor
plus a per-space total pump power sensor. When no source exists for a pump, the
integration MUST omit that pump's power sensor rather than report an incorrect value.

#### Scenario: Explicit power mapping used
- **WHEN** a pump has an explicitly mapped power sensor
- **THEN** the per-pump power sensor mirrors that source's value and unit

#### Scenario: Auto-discovered power source
- **WHEN** a pump has no explicit power mapping but its switch's device exposes a power sensor
- **THEN** the integration uses that sensor for the pump's power reading

#### Scenario: Total pump power
- **WHEN** two pumps have available power readings
- **THEN** the total pump power sensor reports the sum of the available per-pump values

#### Scenario: No power source
- **WHEN** a pump has neither a mapped nor a discoverable power sensor
- **THEN** no power sensor is created for that pump

### Requirement: Pump control service
The integration SHALL provide a `set_pump` service that accepts a grow-space entry
identifier, a pump role, and an action of on, off, or toggle, and actuates the mapped
pump entity accordingly. When the pump role is unmapped or its entity is unavailable,
the service MUST skip the action and log it without raising.

#### Scenario: Service turns a pump off
- **WHEN** `set_pump` is called with the `rdwc_pump` role and action off for a space whose pump is mapped
- **THEN** the integration turns off the mapped entity

#### Scenario: Service skips an unmapped pump
- **WHEN** `set_pump` targets a pump role that is not mapped
- **THEN** the service logs the skip and returns without error

### Requirement: Manual-only actuation
This capability SHALL change pump state only in response to an explicit operator
action, service call, or automation, and SHALL NOT actuate any pump automatically on
its own. Automatic, rule-based pump control is provided by the automations engine.

#### Scenario: No automatic actuation
- **WHEN** the integration loads and pumps are mapped
- **THEN** no pump is turned on or off until an explicit switch, service, or automation command occurs
