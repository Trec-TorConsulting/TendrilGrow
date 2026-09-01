# grow-cultivation-context Specification

## Purpose
Editable, restore-on-restart cultivation-context helper entities per grow space
(growth stage, strain, targets, reservoir volume, nutrients) that ground AI health
checks in operator knowledge that cannot be sensed automatically.
## Requirements
### Requirement: Editable cultivation-context entities
Each grow space SHALL expose editable Home Assistant helper entities for operator
cultivation context: a growth-stage select covering the full cultivation
lifecycle (seedling, mother, clone, vegetative, early_flower, mid_flower,
late_flower, flush, harvest, dry, cure, ready); a stage-started date from which
week-in-stage is computed; numeric context for reservoir volume, site count,
target pH, target EC, feed interval, lights-on hours, and runoff target; and
text context for strain, nutrient line, base nutrients, and additives. These
entities MUST be grouped under the grow space's device. The growth-stage select
MUST default to `vegetative` by name (independent of option ordering) and MUST
render human-readable option labels while persisting snake_case values.
Changing the growth-stage select SHALL reset the stage-started date to today
(the operator MAY then backdate it). Week in stage MUST be derived as elapsed
days since stage-started divided by 7, not as a separately entered number.

#### Scenario: Operator sets growth stage
- **WHEN** the operator selects a growth stage for a grow space
- **THEN** the stage select stores that value and groups under the grow-space device

#### Scenario: Stage change resets stage-started date
- **WHEN** the operator changes the growth stage
- **THEN** the stage-started date is set to today and week-in-stage is recomputed from that date

#### Scenario: Operator selects a mother or clone stage
- **WHEN** the operator sets the stage to `mother` or `clone`
- **THEN** the select stores that value and it is available to AI health checks as growth_stage

#### Scenario: Operator edits numeric and text context
- **WHEN** the operator sets reservoir volume and strain for a grow space
- **THEN** those values are stored on their respective context entities

### Requirement: Context persists across restarts
Cultivation-context entities SHALL restore their last operator-entered value after
a Home Assistant restart.

#### Scenario: Value survives restart
- **WHEN** Home Assistant restarts after the operator set context values
- **THEN** each context entity restores its previously entered value

### Requirement: Context available to AI health checks
The integration SHALL make cultivation context discoverable to AI health checks via
a stable label map keyed by each entity's unique-id suffix, and MUST allow checks
to proceed when context values are unset.

#### Scenario: Context enriches the health prompt
- **WHEN** an AI health check runs and context values are set
- **THEN** those values are included in the prompt under their mapped labels

#### Scenario: Unset context is skipped
- **WHEN** an AI health check runs and some context values are unset
- **THEN** the check proceeds and omits the unset context

