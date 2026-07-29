## ADDED Requirements

### Requirement: HACS-installable custom integration
The system SHALL provide a Home Assistant custom integration located at
`custom_components/tendrilgrow/` that is installable via HACS as a custom
repository and passes Home Assistant `hassfest` and HACS validation.

#### Scenario: Integration passes validation
- **WHEN** the repository is checked by `hassfest` and the HACS validation action
- **THEN** both validations pass with no errors

#### Scenario: Installable via HACS
- **WHEN** a user adds the repository as a HACS custom integration and installs it
- **THEN** the `tendrilgrow` integration becomes available to add in Home Assistant

### Requirement: Valid integration manifest
The integration SHALL include a `manifest.json` declaring the domain
`tendrilgrow`, a name, version, documentation and issue-tracker URLs, code owners,
`config_flow: true`, and an appropriate integration type and iot_class.

#### Scenario: Manifest is well-formed
- **WHEN** Home Assistant loads the integration manifest
- **THEN** all required manifest keys are present and valid

### Requirement: Config-entry lifecycle
The integration SHALL support the async config-entry lifecycle with one config
entry per grow space: it MUST set up from a config entry, forward platform setup
as needed, and cleanly unload and reload without leaking resources or affecting
other grow-space entries.

#### Scenario: Setup and unload
- **WHEN** a grow-space config entry is added and later removed
- **THEN** the integration sets up successfully and unloads without errors

#### Scenario: Reload on options change
- **WHEN** the user updates options for an existing grow-space config entry
- **THEN** that entry reloads and applies the new configuration while other entries keep running

### Requirement: Diagnostics and logging
The integration SHALL log setup, teardown, and configuration events under a
`tendrilgrow` logger and SHALL avoid logging user secrets such as AI provider
API keys.

#### Scenario: Secrets are not logged
- **WHEN** the integration logs configuration or errors
- **THEN** AI provider API keys and other secrets are redacted or omitted
