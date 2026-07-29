## MODIFIED Requirements

### Requirement: Health entities
Each grow space SHALL expose AI health entities: a numeric health-score sensor, a
summary sensor, a feeding-schedule sensor, a last-check timestamp, a critical-alert
binary sensor, and a button to run a check on demand. Entities SHALL refresh when
health state updates and SHALL attach to the shared grow-space device so all of a
space's entities resolve from a single device, without changing their unique ids.

#### Scenario: Score sensor reflects latest result
- **WHEN** a health check completes with a score
- **THEN** the health-score sensor reports that score and refreshes automatically

#### Scenario: Run button triggers a check
- **WHEN** the user presses the "Run AI Health Check" button
- **THEN** a health check is executed for that grow space

#### Scenario: Entities grouped under the grow-space device
- **WHEN** the AI health entities are created for a grow space
- **THEN** they attach to that grow space's device and keep their existing unique ids
