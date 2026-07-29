## ADDED Requirements

### Requirement: Editable cultivation-context entities
Each grow space SHALL expose editable Home Assistant helper entities for operator
cultivation context: a growth-stage select (seedling, vegetative, early_flower,
mid_flower, late_flower, flush); numeric context for week in stage, reservoir
volume, site count, target pH, target EC, feed interval, lights-on hours, and
runoff target; and text context for strain, nutrient line, base nutrients, and
additives. These entities MUST be grouped under the grow space's device.

#### Scenario: Operator sets growth stage
- **WHEN** the operator selects a growth stage for a grow space
- **THEN** the stage select stores that value and groups under the grow-space device

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
