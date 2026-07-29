## ADDED Requirements

### Requirement: Integration-served card bundle
The integration SHALL ship a bundled Lovelace card JavaScript file and register it
as a frontend resource automatically, so the cards are available without the user
manually adding a Lovelace resource. Registration MUST be idempotent and MUST NOT
prevent the integration from loading if the frontend registration fails.

#### Scenario: Cards available after install
- **WHEN** the integration loads after installation and restart
- **THEN** the card bundle is served and registered so the cards appear in the card picker

#### Scenario: Registration failure is non-fatal
- **WHEN** the frontend resource registration fails
- **THEN** the integration still loads and logs the failure

### Requirement: Grow cockpit card
The system SHALL provide a `tendrilgrow-grow-card` that displays, for one grow
space, the AI health score color-coded by severity, the last-check time, the
summary, the latest observations, issues, and recommended actions, the feeding
schedule, the available water-quality metrics, a critical-alert indicator, and a
control to run an AI health check on demand.

#### Scenario: Render a configured grow space
- **WHEN** the card is configured with a grow space that has a recent health result
- **THEN** it shows the score, summary, feeding schedule, and available metrics

#### Scenario: Run a check from the card
- **WHEN** the user activates the card's run control
- **THEN** an AI health check is triggered for that grow space

### Requirement: AI report card
The system SHALL provide a `tendrilgrow-ai-report-card` that displays the detailed
latest AI report — confidence and rationale, observations, issues, recommended
actions, and feeding schedule — and SHALL allow navigating retained history when
more than one result is available.

#### Scenario: Show the detailed report
- **WHEN** the card is configured for a grow space with a health result
- **THEN** it renders the full report with confidence and rationale

#### Scenario: History navigation disabled when unavailable
- **WHEN** only a single result is available
- **THEN** history navigation is disabled rather than erroring

### Requirement: GUI card editors and picker registration
Both cards SHALL provide a GUI configuration editor with a device or entity picker
and SHALL register themselves in the Lovelace card picker with a name, description,
and preview.

#### Scenario: Configure a card via the editor
- **WHEN** the user adds the card through the dashboard UI
- **THEN** a GUI editor lets them pick the grow space without editing YAML

### Requirement: Graceful degradation
The cards SHALL render placeholders instead of errors when referenced entities are
missing, unknown, or unavailable.

#### Scenario: Missing entities
- **WHEN** a grow space has no AI result or a metric entity is unavailable
- **THEN** the card shows a clear placeholder for that element and continues rendering

### Requirement: Reproducible committed bundle
The committed card bundle SHALL be reproducible from source, and continuous
integration SHALL fail when the committed bundle does not match a fresh build.

#### Scenario: Bundle matches source in CI
- **WHEN** CI builds the frontend from source
- **THEN** the build output matches the committed bundle or the CI job fails

### Requirement: Documented example dashboard
The project SHALL provide a documented example dashboard using only built-in Home
Assistant cards as a no-build reference layout.

#### Scenario: Example dashboard is usable
- **WHEN** a user copies the documented example dashboard
- **THEN** it renders TendrilGrow entities using built-in cards without custom resources
