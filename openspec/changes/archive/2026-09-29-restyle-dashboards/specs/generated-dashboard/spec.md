## ADDED Requirements

### Requirement: Zone view is a sections cockpit
For each grow space, the generator MUST emit one Lovelace view with `type: sections`, path `zone-{slug}`, the space title, and icon `mdi:sprout`. Sections MUST follow this order, omitting a section that would contain no entity card: Watch, Lifecycle, AI, Reservoir, Operations, Advisor, Plan. Every card MUST use one of these types: `heading`, `tile`, `gauge`, `picture-entity`, `entities`, `markdown`, `history-graph`.

#### Scenario: Populated space has the cockpit order
- **WHEN** a grow space has a camera, lifecycle helpers, an AI health score, mapped pH, flush entities, and a target band
- **THEN** its view is a sections view whose sections appear in the order Watch, Lifecycle, AI, Reservoir, Operations, Advisor, Plan

#### Scenario: Cards stay on the built-in allowlist
- **WHEN** the generator builds a zone view
- **THEN** every card type is one of `heading`, `tile`, `gauge`, `picture-entity`, `entities`, `markdown`, or `history-graph`

### Requirement: Lifecycle and AI sit above the report
The Lifecycle section MUST tile `ctx_stage`, `ctx_stage_started`, `ctx_week_in_stage`, and `stage_projection` when those suffixes exist, and MUST include a markdown card that templates `projected_stage_end`, `projected_harvest_date`, and `projected_ready_date` from the stage-projection entity. The AI section MUST gauge `ai_health_score` from 0 to 100 with severity thresholds red at 0, yellow at 50, and green at 75, and MUST tile `ai_health_summary`, `ai_health_last_check`, `ai_health_critical_alert`, and `run_ai_health_check` when those suffixes exist. The Advisor section MUST follow Operations and MUST render the score entity's `report` and `feeding_schedule_md` attributes as markdown.

#### Scenario: Score gauge keeps the higher-is-better thresholds
- **WHEN** a grow space has `ai_health_score`
- **THEN** the AI section contains a gauge for that entity with minimum 0, maximum 100, and severity red 0, yellow 50, green 75

#### Scenario: Report is in the Advisor section
- **WHEN** a grow space has `ai_health_score`
- **THEN** the Advisor section contains markdown whose templates read that entity's `report` and `feeding_schedule_md` attributes

### Requirement: Reservoir shows readings against target bands
The Reservoir section MUST tile mapped `ph` and `ec`, then the integration `vpd` entity, before any other mapped sensor role. When `metric_band_ph`, `metric_band_ec`, or `metric_band_vpd` exists, the section MUST tile that problem sensor with its reading. When a target low/high pair exists (`ctx_target_ph_low` and `ctx_target_ph_high`, and the EC and VPD pairs), those number entities MUST appear together in one entities card titled "Target bands", and the legacy single-value `ctx_target_ph` or `ctx_target_ec` MUST NOT appear on the view.

#### Scenario: Primary metrics precede other readings
- **WHEN** a grow space has mapped pH, EC, CF, and an integration VPD entity
- **THEN** the Reservoir section tiles pH, EC, and VPD before CF

#### Scenario: Band sensors and target numbers are present
- **WHEN** a grow space has `metric_band_ph` and both pH target bound entities
- **THEN** the Reservoir section tiles `metric_band_ph` and lists both pH bounds in the Target bands card

#### Scenario: Legacy single target is dropped when the band exists
- **WHEN** a grow space has `ctx_target_ph` and both `ctx_target_ph_low` and `ctx_target_ph_high`
- **THEN** the zone view does not reference `ctx_target_ph`

### Requirement: Operations shows flush and pumps when they exist
The Operations section MUST tile flush suffixes `flush_due`, `days_until_flush`, `days_since_flush`, `next_flush_due`, `last_flush`, `flush_now`, and `flush_interval_days` when each exists. It MUST tile `total_pump_power`, `rdwc_pump`, `chiller_pump`, `air_pump`, and each `{role}_power` suffix when that suffix exists. The section MUST be omitted when the space has none of these suffixes.

#### Scenario: Flush and pump entities are tiled
- **WHEN** a grow space has `flush_due`, `flush_now`, `total_pump_power`, and `rdwc_pump`
- **THEN** the Operations section tiles each of those entities

#### Scenario: No operations section without flush or pumps
- **WHEN** a grow space has no flush suffixes and no pump suffixes
- **THEN** the zone view has no Operations section

### Requirement: Cultivation plan does not repeat the cockpit
The Plan section MUST list remaining cultivation helpers that are not already placed in Lifecycle, Reservoir, or Operations, including strain, water type, site count, reservoir volume, feed interval, lights-on hours, lights-on time, lights-off time, runoff target, nutrient line, base nutrients, and additives when those suffixes exist. An entity MUST appear at most once on a zone view.

#### Scenario: Stage is not listed twice
- **WHEN** a grow space has `ctx_stage` and `ctx_strain`
- **THEN** `ctx_stage` appears only in Lifecycle and `ctx_strain` appears in Plan

### Requirement: Missing entities omit their cards
The generator MUST skip a card when its sensor role or unique-id suffix is absent. It MUST still emit a valid sections view. It MUST keep an entity whose registry entry exists even when the current state is `unavailable` or `unknown`.

#### Scenario: Space without a camera or pumps
- **WHEN** a grow space has lifecycle and AI entities and has no camera, no VPD entity, and no pump suffixes
- **THEN** the zone view has no picture-entity, no VPD tile, and no pump tile, and it still has Lifecycle and AI sections

#### Scenario: Unavailable state stays on the view
- **WHEN** a mapped pH entity is in the registry and its current state is `unavailable`
- **THEN** the Reservoir section still tiles that pH entity

### Requirement: Executive view summarizes every space
The generator MUST emit one Executive view with path `overview`, title Executive, icon `mdi:view-dashboard`, and `type: sections`. It MUST include one section per grow space containing that space's camera when mapped, the AI health gauge when `ai_health_score` exists, and tiles for `ai_health_summary`, `metric_band_summary`, `flush_due`, and `days_until_flush` when those suffixes exist. The view MUST include a badge for each existing `metric_band_summary` and `flush_due`, and each badge MUST have a visibility condition that the same entity's state is `on`. A final section MUST contain one 24-hour history graph of every space's mapped `water_temperature` and `ph`, and that section MUST be omitted when no space has either role.

#### Scenario: Each space gets a status section
- **WHEN** two grow spaces exist and each has an AI health score and a flush-due sensor
- **THEN** the Executive view has a section for each space that gauges that space's score and tiles that space's flush-due sensor

#### Scenario: Badges appear only while the problem is on
- **WHEN** a grow space has `metric_band_summary`
- **THEN** the Executive view has a badge for that entity whose visibility condition requires state `on`

#### Scenario: Trend section tracks water temperature and pH
- **WHEN** any grow space has mapped `water_temperature` or `ph`
- **THEN** the Executive view ends with a history graph of those entities spanning 24 hours

### Requirement: Generation stays opt-in
The generator MUST default to a dry run that writes proposed YAML and does not save Lovelace. A save MUST happen only when `--apply` is passed, and that save MUST be limited to the requested storage-dashboard url path after writing a backup. This capability MUST NOT register a setup-time Lovelace load or save inside the integration.

#### Scenario: Default run does not save
- **WHEN** the generator is invoked without `--apply`
- **THEN** it writes the proposed YAML and does not call the Lovelace save API

#### Scenario: Apply is limited to the named dashboard
- **WHEN** the generator is invoked with `--apply` and `--url-path tendrial-grow`
- **THEN** the Lovelace save targets `tendrial-grow` and a backup of the previous config is written first
