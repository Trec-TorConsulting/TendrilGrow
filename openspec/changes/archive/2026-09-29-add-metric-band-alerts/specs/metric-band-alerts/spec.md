## ADDED Requirements

### Requirement: Out-of-range binary sensors
The integration SHALL expose a problem-class binary sensor for pH, for EC, and for VPD, plus a summary binary sensor that is on when any of those three is on. A metric sensor SHALL be on only when its source has a numeric state outside the active low/high band. It SHALL be off when the value is inside the band. It SHALL be unavailable when the source is unavailable. When the current stage has no band for that metric, the binary sensor SHALL be off.

#### Scenario: pH above the band
- **WHEN** the mapped pH sensor is 6.8 and the active pH band is 5.6 to 6.0
- **THEN** the pH out-of-range binary sensor is on

#### Scenario: VPD inside the band
- **WHEN** canopy VPD is inside the active VPD band
- **THEN** the VPD out-of-range binary sensor is off

#### Scenario: Post-harvest stage has no reservoir band
- **WHEN** the growth stage is `dry` and pH has no stage band
- **THEN** the pH out-of-range binary sensor is off

### Requirement: Band source
The active band MUST be the operator target low/high for that metric when those values are set, and otherwise the current stage's `STAGE_TARGETS` band. Water metrics MUST be read from the mapped entities. For a space bound to a LocalTuya or Tuya Local water monitor, those entities are the local device sensors. Evaluating bands MUST NOT start Tuya cloud polling and MUST NOT read or write LocalTuya config entries.

#### Scenario: Local pH is the source
- **WHEN** the grow space is bound to a LocalTuya device whose pH entity updates
- **THEN** the pH band uses that entity's state and no cloud request is made

#### Scenario: Operator target overrides the stage table
- **WHEN** the stage table says pH 5.6-6.0 and the operator target says 5.8-6.2 and live pH is 6.1
- **THEN** the pH out-of-range sensor is off

### Requirement: Notify on breach with cooldown
The integration SHALL notify when a metric transitions from in-range to out-of-range, and MUST NOT notify again for that metric until the cooldown has elapsed and the metric has returned in range. The default cooldown MUST be 6 hours. Notification MUST NOT turn any control on or off.

#### Scenario: First breach notifies
- **WHEN** EC transitions from inside the band to above the band
- **THEN** the integration sends one notification for EC

#### Scenario: Staying out of range does not repeat
- **WHEN** EC stays above the band across later sensor updates and the cooldown has not elapsed
- **THEN** the integration does not send another EC notification

#### Scenario: No pump command
- **WHEN** a band alert fires
- **THEN** the integration does not call a pump, light, or fan service
