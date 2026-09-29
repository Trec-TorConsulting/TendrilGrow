## ADDED Requirements

### Requirement: Water-type-aware dosing guidance
When cultivation context includes `water_type`, AI health checks SHALL include
brief source-water grounding in the dosing rules (for example, mineral-free
sources such as RO/distilled/rain imply Cal-Mag priority; tap/well/spring imply
accounting for baseline minerals).

#### Scenario: RO water type influences feeding guidance
- **WHEN** an AI health check builds a prompt and water_type is `ro`
- **THEN** the prompt includes source-water grounding that treats RO as a
  near-zero mineral baseline requiring calcium/magnesium supplementation
