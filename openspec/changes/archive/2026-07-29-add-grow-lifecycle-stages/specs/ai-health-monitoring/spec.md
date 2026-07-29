## MODIFIED Requirements

### Requirement: Health check execution
A health check SHALL capture a snapshot from the mapped camera, collect mapped
sensor metric states and operator cultivation context, build an agronomy prompt
whose primary objective is selected by the current growth stage and which is
calibrated to that stage's target ranges when defined, call the provider's vision
report generation, and parse the response into a structured result containing
score, confidence, severity, summary, observations, issues, recommended actions,
and a feeding schedule. The stage objective MUST frame mother plants as permanent
vegetative stock that are never flowered, clones as rooting cuttings, flowering
stages as quality-first, and post-harvest stages (harvest, dry, cure, ready) as
drying/curing assessment. A stage without reservoir targets MUST still produce a
check using best-practice guidance rather than failing.

#### Scenario: Successful check produces a structured result
- **WHEN** the provider returns a valid JSON report
- **THEN** the check stores a result with score, severity, summary, and feeding schedule

#### Scenario: Stage selects the prompt objective
- **WHEN** a health check runs for a grow space whose stage is `mother` or `clone`
- **THEN** the prompt's primary objective targets mother health/structure or clone rooting rather than flower quality

#### Scenario: Stage without reservoir targets still runs
- **WHEN** a health check runs for a post-harvest stage (dry or cure) that has no pH/EC/VPD targets
- **THEN** the check proceeds using best-practice guidance and does not error

#### Scenario: Non-JSON response is tolerated
- **WHEN** the provider returns text that is not valid JSON
- **THEN** the check records an "unknown" result carrying the raw text without error
