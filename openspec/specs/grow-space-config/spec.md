# grow-space-config Specification

## Purpose
The UI config and options flows that create and edit grow spaces as one Home
Assistant config entry per space, mapping the user's own entities to roles with no
hardcoded entity ids.
## Requirements
### Requirement: One config entry per grow space
The integration SHALL represent each grow space as its own Home Assistant config
entry so that each space owns its equipment mappings, grow type, targets, and
settings independently and can be reloaded, enabled, or removed on its own.

#### Scenario: Each grow space is a separate entry
- **WHEN** a user creates two grow spaces
- **THEN** each grow space exists as its own config entry with independent settings

#### Scenario: Reload one space without affecting others
- **WHEN** the user changes settings for one grow space and it reloads
- **THEN** other grow-space entries continue running unaffected

### Requirement: Guided config flow
The integration SHALL provide a UI config flow that lets a user create a grow space
as a new config entry, without editing YAML or entering any hardcoded entity ids.

#### Scenario: Create a grow space
- **WHEN** a user adds the TendrilGrow integration
- **THEN** the config flow guides them to name a grow space and map their entities,
  and creates a config entry for that space on completion

#### Scenario: Prevent duplicate setup conflicts
- **WHEN** a user attempts to create a grow space whose name already exists
- **THEN** the config flow rejects the duplicate and prompts for a unique name

### Requirement: User-mapped entities
The config flow and options flow SHALL let the user map their own Home Assistant
entities to grow-space roles (for example: temperature, humidity, light/PPFD,
pH, EC/TDS, camera, and controllable lights/fans). The integration MUST NOT assume
fixed entity ids.

#### Scenario: Map existing HA entities
- **WHEN** the user selects a role and picks an entity from their Home Assistant
- **THEN** the selected entity is stored as the mapping for that role in the grow space

#### Scenario: Optional roles left unmapped
- **WHEN** the user leaves an optional role unmapped
- **THEN** the grow space is still created and features depending on that role are
  gracefully skipped

### Requirement: Options flow for editing
The integration SHALL provide an options flow that lets the user edit a grow
space's mappings and per-space settings after initial setup, applying changes
without requiring reinstallation. Adding or removing grow spaces is done by adding
or removing config entries.

#### Scenario: Edit an existing grow space
- **WHEN** the user opens the options for a grow-space entry and changes a mapping or target
- **THEN** the change is saved and that grow-space entry reloads to apply it

#### Scenario: Remove a grow space
- **WHEN** the user deletes a grow-space config entry
- **THEN** that grow space and its mappings are removed and other spaces are unaffected

### Requirement: Per-space configuration
Each grow space SHALL store its own configuration including grow type, the mapped
sensors and controls, and optional targets/schedules, independent of other spaces.

#### Scenario: Independent space settings
- **WHEN** two grow spaces are configured with different grow types and targets
- **THEN** each space retains and uses its own settings independently

