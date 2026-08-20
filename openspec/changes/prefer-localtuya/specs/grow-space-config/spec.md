## ADDED Requirements

### Requirement: Local water-monitor device selector
The config flow and options flow SHALL let the user bind one Home Assistant device
from LocalTuya (`localtuya`) or Tuya Local (`tuya_local`) as that grow space's
water monitor. The selector MUST NOT require hardcoded entity ids. Cloud Tuya
credential fields remain available as an optional fallback when no local device
is selected. New grow spaces MUST default Tuya cloud polling to disabled.

#### Scenario: Select a LocalTuya device
- **WHEN** the user picks a LocalTuya water-monitor device in the mapping step
- **THEN** that Home Assistant device id is stored on the grow-space entry as the
  water-metric source

#### Scenario: Cloud fields remain as fallback
- **WHEN** the user does not select a local water-monitor device
- **THEN** the flow still allows enabling Tuya cloud polling and mapping water
  roles manually

#### Scenario: New spaces do not enable cloud polling by default
- **WHEN** a user creates a grow space and does not opt into Tuya cloud polling
- **THEN** Tuya cloud polling is stored as disabled

### Requirement: Water mapping fields stay editable with a local source
When a local water-monitor device is bound, the config and options flows MUST
show the water-quality sensor-mapping fields so the operator can override
auto-mapped datapoints. Those fields SHALL be hidden only when Tuya cloud
polling is the effective water source (no local device bound). Canopy
temperature, humidity, and camera mappings remain manual in every case.

#### Scenario: Override a local auto-map
- **WHEN** a local water-monitor device is bound and the user maps the pH role to
  a different entity
- **THEN** the grow space stores that entity id for pH and does not replace it on
  reload

#### Scenario: Cloud fallback hides water fields
- **WHEN** Tuya cloud polling is enabled and no local water-monitor device is bound
- **THEN** the flow hides the manual water-quality mapping fields
