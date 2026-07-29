# grow-lifecycle-projection Specification

## Purpose
TBD - created by archiving change add-grow-lifecycle-stages. Update Purpose after archive.
## Requirements
### Requirement: Default per-stage durations
The integration SHALL define default typical durations, in days, for each
lifecycle stage that has a bounded length, and SHALL treat `mother` and `ready`
as indefinite/terminal with no duration. These defaults MAY be tuned by a future
change but SHALL provide a reasonable estimate out of the box.

#### Scenario: Bounded stage has a default duration
- **WHEN** the projection reads the duration for `vegetative`
- **THEN** a positive default number of days is returned

#### Scenario: Indefinite stage has no duration
- **WHEN** the projection reads the duration for `mother`
- **THEN** no duration is defined and the stage is treated as indefinite

### Requirement: Projected timeline sensor
Each grow space SHALL expose a stage-projection sensor whose value is the days
remaining in the current stage, derived from the current growth stage and the
operator-entered week-in-stage, grouped under the grow space's device. The sensor
SHALL expose attributes for days-in-stage, days-remaining, projected stage-end
date, projected harvest date, and projected ready date, computed along the
biological pipeline (clone → seedling → vegetative → early_flower → mid_flower →
late_flower → flush → harvest → dry → cure → ready).

#### Scenario: Days remaining reflects stage and week-in-stage
- **WHEN** the stage is `vegetative` and week-in-stage indicates part of the stage has elapsed
- **THEN** the sensor reports the remaining days and a projected stage-end date

#### Scenario: Projected harvest and ready dates
- **WHEN** the stage is a pre-harvest pipeline stage
- **THEN** the attributes include projected harvest and ready dates that sum the remaining pipeline durations

#### Scenario: Indefinite or terminal stage
- **WHEN** the stage is `mother` or `ready`
- **THEN** the sensor value is unknown and no projected dates are asserted

