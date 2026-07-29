# ai-health-monitoring Specification

## Purpose
Scheduled and on-demand camera-based AI grow-health monitoring: snapshot capture,
quality-first agronomy prompting calibrated to per-stage targets, structured
scoring and dynamic feeding schedules, result persistence and retention, health
entities, and critical-score notifications.
## Requirements
### Requirement: Camera-based health check preconditions
An AI health check SHALL run only when the grow space has a configured AI provider
and model and a mapped camera role. When any precondition is missing the check
MUST fail with an actionable error and MUST NOT send a provider request.

#### Scenario: Missing provider or model
- **WHEN** a health check is requested but no provider/model is configured
- **THEN** the check fails with a not-configured error and makes no provider call

#### Scenario: Missing camera
- **WHEN** a health check is requested but no camera role is mapped
- **THEN** the check fails with a camera-not-configured error

### Requirement: Health check execution
A health check SHALL capture a snapshot from the mapped camera, collect mapped
sensor metric states and operator cultivation context, build a quality-first
agronomy prompt calibrated to per-stage target ranges, call the provider's vision
report generation, and parse the response into a structured result containing
score, confidence, severity, summary, observations, issues, recommended actions,
and a feeding schedule.

#### Scenario: Successful check produces a structured result
- **WHEN** the provider returns a valid JSON report
- **THEN** the check stores a result with score, severity, summary, and feeding schedule

#### Scenario: Non-JSON response is tolerated
- **WHEN** the provider returns text that is not valid JSON
- **THEN** the check records an "unknown" result carrying the raw text without error

### Requirement: Result persistence and retention
The integration SHALL persist health results per grow space, expose the latest
result and history count, and trim history to a configurable retention window on
each run.

#### Scenario: History bounded by retention window
- **WHEN** results older than the retention window exist after a new check
- **THEN** those results are removed and only in-window results are retained

#### Scenario: Latest result survives restart
- **WHEN** Home Assistant restarts after a check has run
- **THEN** the latest result and history are restored from storage

### Requirement: Health entities
Each grow space SHALL expose AI health entities: a numeric health-score sensor, a
summary sensor, a feeding-schedule sensor, a last-check timestamp, a critical-alert
binary sensor, and a button to run a check on demand. Entities SHALL refresh when
health state updates.

#### Scenario: Score sensor reflects latest result
- **WHEN** a health check completes with a score
- **THEN** the health-score sensor reports that score and refreshes automatically

#### Scenario: Run button triggers a check
- **WHEN** the user presses the "Run AI Health Check" button
- **THEN** a health check is executed for that grow space

### Requirement: Critical-score notifications
The integration SHALL notify when a result's score is at or below the configured
severe threshold: it MUST create a persistent notification and, when a notify
service is configured, MUST also call that notify service.

#### Scenario: Persistent notification on critical score
- **WHEN** a check returns a score at or below the severe threshold
- **THEN** a persistent notification is created for that grow space

#### Scenario: Optional notify service
- **WHEN** a notify service is configured and a critical score occurs
- **THEN** the integration also calls that notify service

### Requirement: Scheduled and on-demand checks
The integration SHALL run health checks periodically on a configurable interval,
run one delayed check after startup, and provide a `run_ai_health_check` service
to run a check for a specified loaded entry or all loaded entries.

#### Scenario: Periodic check runs on interval
- **WHEN** the configured interval elapses
- **THEN** a scheduled health check runs for the grow space

#### Scenario: Service runs all entries
- **WHEN** the `run_ai_health_check` service is called without an entry id
- **THEN** a check runs for every loaded grow-space entry

