## ADDED Requirements

### Requirement: Grow space model
The system SHALL model a grow space as a named container with a grow type (for
example RDWC, soil, coco, other), a physical descriptor (for example tent size),
and a collection of zones/sites, mapped sensors, and mapped controls.

#### Scenario: Represent a reference tent
- **WHEN** a 4x4 RDWC tent with 4 sites, a 400W light, and a camera is configured
- **THEN** the model stores the grow type, size, four sites, and the mapped
  light and camera under one grow space

#### Scenario: Support varied grow types
- **WHEN** a user configures a non-RDWC grow type
- **THEN** the model accepts it without requiring RDWC-specific fields

### Requirement: Zones and sites
A grow space SHALL support zero or more zones/sites representing individual plants
or growing positions, each optionally carrying its own metadata.

#### Scenario: Add plant sites
- **WHEN** a grow space is configured with two mother plants
- **THEN** the model records two sites within that space

### Requirement: Sensor and control roles
The model SHALL define an extensible set of sensor roles (including temperature,
humidity/VPD, light PPFD/lux, pH, EC/TDS, and camera) and control roles (including
lights, fans, and inline fans), each bound to a user-mapped entity id.

#### Scenario: Bind a sensor role to an entity
- **WHEN** a temperature role is mapped to a user's temperature sensor entity
- **THEN** the model resolves that role to the mapped entity's state

#### Scenario: Extensible roles
- **WHEN** a new sensor or control role is needed
- **THEN** it can be added to the role set without breaking existing grow spaces

### Requirement: Derived metrics
The model SHALL compute derived metrics from mapped sensors where inputs exist,
including Vapor Pressure Deficit (VPD) from temperature and humidity.

#### Scenario: Compute VPD
- **WHEN** a grow space has mapped temperature and humidity sensors with valid states
- **THEN** the model exposes a computed VPD value for that space

#### Scenario: Missing inputs
- **WHEN** a required input for a derived metric is unmapped or unavailable
- **THEN** the derived metric reports unavailable rather than an incorrect value

### Requirement: Targets and schedules
Each grow space SHALL optionally store target ranges (for example VPD, pH, EC) and
light schedules used later by dashboards, AI advice, and automations.

#### Scenario: Store target ranges
- **WHEN** a user sets a target VPD range for a grow space
- **THEN** the range is persisted with that space and available to consumers
