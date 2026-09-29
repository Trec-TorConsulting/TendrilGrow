## MODIFIED Requirements

### Requirement: User-mapped entities
The config flow and options flow SHALL let the user map their own Home Assistant
entities to grow-space roles (for example: temperature, humidity, light/PPFD,
pH, EC/TDS, camera, and controllable lights/fans). The integration MUST NOT assume
fixed entity ids. An options save MUST deep-merge mappings: roles shown on the
form update or clear from that submission, and roles not shown on the form MUST
remain as previously stored.

#### Scenario: Map existing HA entities
- **WHEN** the user selects a role and picks an entity from their Home Assistant
- **THEN** the selected entity is stored as the mapping for that role in the grow space

#### Scenario: Optional roles left unmapped
- **WHEN** the user leaves an optional role unmapped
- **THEN** the grow space is still created and features depending on that role are
  gracefully skipped

#### Scenario: Hidden water roles survive an options save
- **WHEN** the options form does not display water-quality roles and the grow space already has a pH mapping
- **THEN** the stored pH mapping is unchanged after the options save

### Requirement: Options flow for editing
The integration SHALL provide an options flow that lets the user edit a grow
space's mappings and per-space settings after initial setup, applying changes
without requiring reinstallation. Adding or removing grow spaces is done by adding
or removing config entries. After an options save, every platform and service for
that entry MUST read the merged config (`entry.data` overlaid by `entry.options`),
not `entry.data` alone.

#### Scenario: Edit an existing grow space
- **WHEN** the user opens the options for a grow-space entry and changes a mapping or target
- **THEN** the change is saved and that grow-space entry reloads to apply it

#### Scenario: Remove a grow space
- **WHEN** the user deletes a grow-space config entry
- **THEN** that grow space and its mappings are removed and other spaces are unaffected

#### Scenario: Pump mapped only in options
- **WHEN** the operator maps `rdwc_pump` in the options flow and `entry.data` has no pump mapping
- **THEN** the reloaded entry exposes a pump switch bound to that entity
