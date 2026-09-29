## MODIFIED Requirements

### Requirement: Camera-based health check preconditions
An AI health check SHALL run only when the grow space has a configured AI provider
and model and a mapped camera role. When any precondition is missing the check
MUST fail with an actionable error and MUST NOT send a provider request. The
startup check and the interval scheduler MUST NOT be started when the provider
is unset or the model is empty.

#### Scenario: Missing provider or model
- **WHEN** a health check is requested but no provider/model is configured
- **THEN** the check fails with a not-configured error and makes no provider call

#### Scenario: Missing camera
- **WHEN** a health check is requested but no camera role is mapped
- **THEN** the check fails with a camera-not-configured error

#### Scenario: Startup does not call the provider when AI is off
- **WHEN** a grow space is set up with no AI provider
- **THEN** the integration does not schedule a startup health check

## ADDED Requirements

### Requirement: One health check at a time
The integration MUST NOT start a second health check for a grow space while one is running. The in-flight flag MUST be cleared when the check finishes or raises.

#### Scenario: Button pressed during a scheduled check
- **WHEN** a scheduled check is running and the operator starts another check
- **THEN** the second start does not send another provider request

### Requirement: Structured list fields
The integration MUST treat `issues`, `recommended_actions`, `observations`, and `feeding_schedule` as lists of strings. A single string MUST be stored as one entry. A non-list value MUST be stored as an empty list. A Markdown code fence around JSON MUST be removed as fence lines and MUST NOT strip backtick characters from inside the JSON.

#### Scenario: Model returns issues as one string
- **WHEN** the model JSON contains `"issues": "tip burn"`
- **THEN** the stored issues list is exactly `["tip burn"]`

#### Scenario: Fenced JSON still parses
- **WHEN** the model wraps the JSON object in a ```json fence
- **THEN** the integration parses the object and keeps string values intact
