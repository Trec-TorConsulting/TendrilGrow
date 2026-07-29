## MODIFIED Requirements

### Requirement: Sensor and control roles
The model SHALL define an extensible set of sensor roles — including temperature,
humidity/VPD, light PPFD/lux, camera, and the distinct water-quality roles `ph`,
`ec`, `cf`, `orp`, and `tds` — and control roles — including lights, fans, inline
fans, and the pump roles `rdwc_pump`, `chiller_pump`, and `air_pump` — each bound to
a user-mapped entity id. The model SHALL migrate the legacy combined `ec_tds` role to
the `tds` role when loading older config data.

#### Scenario: Bind a sensor role to an entity
- **WHEN** a temperature role is mapped to a user's temperature sensor entity
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
