## MODIFIED Requirements

### Requirement: Editable cultivation-context entities
Each grow space SHALL expose editable Home Assistant helper entities for operator
cultivation context: a growth-stage select covering the full cultivation
lifecycle (seedling, mother, clone, vegetative, early_flower, mid_flower,
late_flower, flush, harvest, dry, cure, ready); a water-type select covering
makeup water sources (tap, ro, filtered, bottled, rain, well, distilled,
spring, mixed); numeric context for week in stage, reservoir volume, site
count, target pH, target EC, feed interval, lights-on hours, and runoff
target; and text context for strain, nutrient line, base nutrients, and
additives. These entities MUST be grouped under the grow space's device. The
growth-stage select MUST default to `vegetative` by name (independent of option
ordering) and MUST render human-readable option labels while persisting
snake_case values. The water-type select MUST default to `tap` by name
(independent of option ordering) and MUST render human-readable option labels
while persisting snake_case values.

#### Scenario: Operator sets growth stage
- **WHEN** the operator selects a growth stage for a grow space
- **THEN** the stage select stores that value and groups under the grow-space device

#### Scenario: Operator selects a mother or clone stage
- **WHEN** the operator sets the stage to `mother` or `clone`
- **THEN** the select stores that value and it is available to AI health checks as growth_stage

#### Scenario: Operator sets water type
- **WHEN** the operator selects a water type for a grow space
- **THEN** the water-type select stores that value and groups under the grow-space device

#### Scenario: Operator edits numeric and text context
- **WHEN** the operator sets reservoir volume and strain for a grow space
- **THEN** those values are stored on their respective context entities

## ADDED Requirements

### Requirement: Water-type context available to AI
The integration SHALL map the water-type select unique-id suffix into the
cultivation-context label map as `water_type` so AI health checks can include
the operator's makeup water source when set.

#### Scenario: Water type enriches the health prompt
- **WHEN** an AI health check runs and water type is set
- **THEN** the prompt includes the value under the `water_type` label
