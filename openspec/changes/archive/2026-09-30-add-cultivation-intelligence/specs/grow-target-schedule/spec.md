## ADDED Requirements

### Requirement: Drying and curing stage target bands
The system SHALL seed default target bands for `dry` and `cure` growth stages adhering to the 60/60 rule (target VPD 0.65–0.78 kPa, representing 60°F / 60% RH). When the grow space enters `dry` or `cure`, target VPD low MUST default to 0.65 kPa and target VPD high MUST default to 0.78 kPa if not previously customized by the operator.

#### Scenario: Seeding 60/60 targets in dry stage
- **WHEN** a grow space transitions to `dry` without customized VPD bands
- **THEN** target VPD low seeds to 0.65 kPa and target VPD high seeds to 0.78 kPa

#### Scenario: Seeding 60/60 targets in cure stage
- **WHEN** a grow space transitions to `cure` without customized VPD bands
- **THEN** target VPD low seeds to 0.65 kPa and target VPD high seeds to 0.78 kPa
