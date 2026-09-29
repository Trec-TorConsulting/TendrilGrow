# grow-data-model Specification

## Purpose
The flexible domain model for grow spaces: sites, an extensible set of sensor and
control roles bound to user-mapped entities, derived metrics (VPD), and per-space
targets and schedules.
## Requirements
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
The model SHALL define an extensible set of sensor roles — including the **air
(canopy)** roles `temperature` and `humidity` (used for VPD), a distinct
`water_temperature` role for the reservoir/water probe, light PPFD/lux, camera, and
the distinct water-quality roles `ph`, `ec`, `cf`, `orp`, and `tds` — and control
roles — including lights, fans, inline fans, and the pump roles `rdwc_pump`,
`chiller_pump`, and `air_pump` — each bound to a user-mapped entity id.
Water/reservoir temperature MUST NOT be bound to the air `temperature` role. The
model SHALL migrate the legacy combined `ec_tds` role to the `tds` role when loading
older config data.

#### Scenario: Bind a sensor role to an entity
- **WHEN** an air temperature role is mapped to a user's canopy temperature sensor
- **THEN** the model resolves that role to the mapped entity's state

#### Scenario: Distinct water-quality roles
- **WHEN** a grow space maps pH, EC, CF, ORP, and TDS probes
- **THEN** the model stores each as its own role bound to its own entity id

#### Scenario: Bind a pump control role
- **WHEN** a grow space maps the `rdwc_pump` role to a switch entity
- **THEN** the model stores it as a control role bound to that entity id

#### Scenario: Legacy EC/TDS role migrated
- **WHEN** a stored grow space contains a legacy `ec_tds` mapping and no `tds` mapping
- **THEN** loading the model migrates that entity id to the `tds` role

#### Scenario: Extensible roles
- **WHEN** a new sensor or control role is needed
- **THEN** it can be added to the role set without breaking existing grow spaces

### Requirement: Derived metrics
The model SHALL compute derived metrics from mapped sensors where inputs exist,
including Vapor Pressure Deficit (VPD) computed from the **air** temperature and
**air** relative humidity. VPD computation MUST be unit-aware, converting Fahrenheit
readings to Celsius before calculating, and the integration SHALL expose the computed
VPD as a per-grow-space sensor. When a required input is unmapped or invalid, the
derived metric MUST report unavailable rather than an incorrect value.

#### Scenario: Compute VPD from air climate
- **WHEN** a grow space has mapped air temperature and air humidity sensors with valid states
- **THEN** the model exposes a computed VPD value for that space

#### Scenario: Unit-aware conversion
- **WHEN** the mapped air temperature reports in Fahrenheit
- **THEN** the VPD is computed after converting the temperature to Celsius

#### Scenario: Missing inputs
- **WHEN** a required input for a derived metric is unmapped or unavailable
- **THEN** the derived metric reports unavailable rather than an incorrect value

### Requirement: Targets and schedules
Each grow space SHALL optionally store target ranges (for example VPD, pH, EC) and
light schedules used later by dashboards, AI advice, and automations.

#### Scenario: Store target ranges
- **WHEN** a user sets a target VPD range for a grow space
- **THEN** the range is persisted with that space and available to consumers

