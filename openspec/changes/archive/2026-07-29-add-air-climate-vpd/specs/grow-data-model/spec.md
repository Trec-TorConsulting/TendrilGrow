## MODIFIED Requirements

### Requirement: Sensor and control roles
The model SHALL define an extensible set of sensor roles — including the **air
(canopy)** roles `temperature` and `humidity` (used for VPD), a distinct
`water_temperature` role for the reservoir/water probe, light PPFD/lux, camera, and
the distinct water-quality roles `ph`, `ec`, `cf`, `orp`, and `tds` — and control
roles (including lights, fans, and inline fans), each bound to a user-mapped entity
id. Water/reservoir temperature MUST NOT be bound to the air `temperature` role. The
model SHALL migrate the legacy combined `ec_tds` role to the `tds` role when loading
older config data.

#### Scenario: Bind a sensor role to an entity
- **WHEN** an air temperature role is mapped to a user's canopy temperature sensor
- **THEN** the model resolves that role to the mapped entity's state

#### Scenario: Air and water temperature are distinct
- **WHEN** a grow space has both a canopy air-temperature probe and a reservoir water-temperature probe
- **THEN** the model stores them under the separate `temperature` and `water_temperature` roles

#### Scenario: Distinct water-quality roles
- **WHEN** a grow space maps pH, EC, CF, ORP, and TDS probes
- **THEN** the model stores each as its own role bound to its own entity id

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
