## ADDED Requirements

### Requirement: No automatic dashboard writes
The integration MUST NOT load a Lovelace dashboard in order to save it, and MUST NOT call a dashboard save API during setup, reload, or entity migration.

#### Scenario: Setup does not save dashboards
- **WHEN** a grow space config entry finishes setup
- **THEN** the integration does not save any Lovelace dashboard

### Requirement: Repair for retired stage-clock entity ids
When a storage-mode dashboard still references a retired TendrilGrow week-in-stage entity id, the integration SHALL raise a repair issue that includes the retired id and the replacement stage-clock entity id. The repair MUST be removed when a later read-only scan no longer finds that retired id. Creating the repair MUST NOT modify the dashboard.

#### Scenario: Stale entity id raises a repair
- **WHEN** a storage dashboard references the retired week-in-stage number entity and a replacement stage-clock entity exists
- **THEN** a repair issue names both entity ids and the dashboard config is unchanged

#### Scenario: Repair clears after the card is updated
- **WHEN** a later scan finds no retired stage-clock ids
- **THEN** the repair issue is dismissed
