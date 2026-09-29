## MODIFIED Requirements

### Requirement: Context available to AI health checks
The integration SHALL make cultivation context discoverable to AI health checks via
a stable label map keyed by each entity's unique-id suffix, and MUST allow checks
to proceed when context values are unset. When operator target bands or light
on/off times are set, the prompt MUST include them.

#### Scenario: Context enriches the health prompt
- **WHEN** an AI health check runs and context values are set
- **THEN** those values are included in the prompt under their mapped labels

#### Scenario: Unset context is skipped
- **WHEN** an AI health check runs and some context values are unset
- **THEN** the check proceeds and omits the unset context

#### Scenario: Target band is in the prompt
- **WHEN** an AI health check runs and the operator EC band is set
- **THEN** the prompt includes that EC band
