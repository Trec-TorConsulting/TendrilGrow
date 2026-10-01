# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and semantic versioning.

## [Unreleased]

## [0.3.15] - 2026-10-01

### Added
- **Dedicated Standalone AI Agronomist Chat Card (`<tendrilgrow-chat-card>`)**:
  - Independent 2-way AI agronomist chat window grounded in live tent telemetry (pH, EC, VPD, Air/Water Temp, Days Since Flush).
  - Bypasses Home Assistant voice intent matchers (`conversation.home_assistant`) to eliminate device control error messages (*"Sorry, I see you're referring to Light..."*).
  - Stage-specific canopy defoliation & trimming guidance (`should I trim now or wait?`) with clear recommendations per stage.
  - Deep VPD suppression alerts & transpiration diagnostics for mid-flower mold/botrytis prevention.
  - Color-accented chat markdown typography parser for styled headers, dividers, and step-by-step horticultural protocols.
- **Horticultural Water Prep & Nutrient Mixing Order Protocol**:
  - Locked-in 8-step chemical mixing sequence in the Feeding Recipe tab (Silica first $\rightarrow$ wait 15 min $\rightarrow$ Cal-Mag second $\rightarrow$ Micro $\rightarrow$ Grow $\rightarrow$ Bloom $\rightarrow$ Additives $\rightarrow$ Hydroguard $\rightarrow$ pH Buffer last) to prevent salt precipitation and nutrient lockout.
- **Ultimate HACS Digital Twin & Cockpit Frontend**:
  - Bundled custom Lovelace cards directly within the integration: `<tendrilgrow-twin-card>`, `<tendrilgrow-overview-card>`, `<tendrilgrow-plan-card>`, `<tendrilgrow-chat-card>`.
  - Automatic frontend resource injection via `StaticPathConfig` (`/tendrilgrow_static/`) and `add_extra_js_url`.
  - Interactive 2.5D visual grow tent schematic HUD with dynamic fan animation, quantum LED light beam, glassmorphism telemetry capsule, and cutaway reservoir.
  - Responsive multi-device ergonomics for mobile phones, wall tablets, and desktop displays.

## [0.3.14] - 2026-09-30

### Added
- **Ultimate Zone Cockpit Dashboards**:
  - Overhauled `/tendrial-grow/zone-3x3_mothers_tent` and `/tendrial-grow/zone-4x4_full_cycle_tent` into 9-section cockpits while keeping the Executive Overview intact.
  - Interactive equipment controls: Grow light tile with brightness slider, Circulation and Inline Duct fan tiles with speed sliders, and power-strip RDWC, air, and chiller pump controls.
  - Vivosun controller plan schedule status cards for light, circulation, and duct fan automated programming.
  - In-place cultivation controls: growth stage selector, stage start date picker, target setpoint band editors (pH, EC, VPD), flush operations with interval controls, and cultivation parameter forms.
  - Native Home Assistant to-do list card integration (`todo.<grow>_grow_tasks`) for tracking zone chores.
  - Full cultivation telemetry display: 7-parameter water monitoring, derived canopy & leaf VPD, dew point margin, mold risk alerts, photoperiod hours, 12/12 flip tracking, and ambient lung room monitoring.
  - Dual 24-hour history graphs for canopy microclimate and hydroponic reservoir chemistry.
  - Automated dynamic discovery in `scripts/generate_dashboard.py` supporting both `light` and `switch` domain pump entities and Vivosun controllers.

## [0.3.13] - 2026-09-30

### Added
- Cultivation Intelligence suite (`add-cultivation-intelligence`):
  - **RDWC EC vs. pH Drift Diagnostic Engine**: Analyzes rolling 12h–24h trends in EC and pH; classifies conditions into `equilibrium`, `dilute_recommended` (transpiration outstripping uptake), `feed_recommended` (hungry plants), and `root_health_check` (acute acid plunge < 5.2 or sudden drops indicating anaerobic pathogens/Pythium). Exposes `sensor.<grow>_reservoir_drift_diagnosis`.
  - **Leaf Surface Temperature & True Leaf VPD**: Computes physiological leaf VPD using mapped infrared leaf temperature probes (`SENSOR_ROLE_LEAF_TEMPERATURE`) or configurable LED offset (`CONF_LEAF_TEMP_OFFSET`, default -3.0°F / -1.67°C). Exposes `sensor.<grow>_leaf_vpd`.
  - **Powdery Mildew & Botrytis Risk Index**: Derives dew point margin ($T_{leaf/air} - T_{dew}$); flags `binary_sensor.<grow>_mold_risk` on critical condensation margins (< 2.0°C / 3.6°F) or elevated relative humidity (≥ 65%) during vulnerable flowering, drying, and curing stages. Exposes `sensor.<grow>_dew_point_margin`.
  - **Photoperiod & 12/12 Flip Tracking**: Exposes dynamic `sensor.<grow>_photoperiod_hours` and automatically tracks `sensor.<grow>_days_since_flip` for flowering stages.
  - **Reservoir Water Level & Daily Transpiration Rate**: Adds `SENSOR_ROLE_WATER_LEVEL`, calculates `sensor.<grow>_transpiration_rate_daily`, and flags stalled water consumption as an early warning for root rot or hypoxia.
  - **60/60 Harvest Drying & Curing Phase**: Automatically seeds target VPD bands (0.65–0.78 kPa) adhering to the 60°F ± 2°F and 60% RH ± 3% gold standard for terpene preservation in `dry` and `cure` stages.


### Fixed
- Config flow entity mapping: apply `_optional_entity_field` to initial setup flow (`async_step_entity_mapping`) so multi-leak selection and flow domain filters are consistent between initial setup and options flow.
- Config flow list serialization: normalize list values to comma-space separated strings on initial setup to avoid bracket formatting artifacts.
- Water safety flow presence: treat `unavailable` and `unknown` sensor states as indeterminate (`None`) rather than zero-flow to prevent false no-flow trips during wireless sensor reconnects.
- Water safety dispatcher deduplication: streamline status dispatch calls so state transitions only trigger a single update per evaluation cycle.
- AI health check telemetry: safely handle multi-leak sensor mappings in `_collect_metric_state_values` avoiding invalid entity lookups when multiple sensors are mapped.
- Diagnostics: expose consistent `shutoff_enabled` key matching live validation requirements.

## [0.3.11] - 2026-09-29

### Added
- Water safety monitoring (`add-water-safety-monitoring`):
  - Multi-leak detection supporting multiple leak sensors per grow space (tent floor, chiller pan, reservoir edge) with configurable debounce.
  - Flow verification: tracks return-line flow sensors (numeric rate or binary switch) when RDWC circulation pumps run, raising a `no_flow` safety alert after a configurable grace period.
  - Opt-in emergency RDWC pump shutoff: automatically commands the mapped circulation pump `turn_off` once upon confirmed leak detection, preventing flooding or draining the reservoir (never auto-restarts).
  - Safety entities: `binary_sensor.<grow>_flow_ok`, `binary_sensor.<grow>_leak_detected`, and `sensor.<grow>_water_safety_status` with detailed attributes (`active_leaks`, `flow_rate`, `shutoff_triggered`).
  - Diagnostic dump for water safety and live HA validation script support.

## [0.3.10] - 2026-09-29

### Fixed
- Local water monitor auto-mapping: pass `runtime.auto_mapped_sensor_roles` during setup and allow `auto_mapped_store` to default gracefully, ensuring Tuya Local and LocalTuya water sensors (pH, EC, TDS, ORP, CF, water temperature) automatically bind to grow spaces on startup without throwing a silent `TypeError`.


### Fixed
- AI health checks: guard scheduler against unconfigured providers, prevent overlapping concurrent runs with single-flight locks, add provider timeouts, and pass Gemini API keys securely via headers.
- Dashboards: eliminate unprompted Lovelace file rewrites during setup; register non-destructive Home Assistant repairs when retired entity IDs are detected.

### Changed
- Refactored sensor platform into domain-specific submodules (`ai`, `environment`, `flush`, `pump_power`, `stage`, `timelapse`, `tuya`) and isolated services and stage migration logic.

## [0.3.8] - 2026-09-25

### Changed
- AI health checks score against the operator's pH, EC, and air-VPD bands.
  The built-in stage ranges apply only when those bands are unset.
- Flora mixes are the current stage only, labeled as a light feed under
  General Hydroponics' published charts. CalMag+ 2.5 ml/gal is half the
  Botanicare label rate. The check does not print an estimated EC.
- A rising reservoir EC is treated as concentration, not a reason to add
  nutrients. Checks include DLI, dew point, pump and light state, and the
  previous telemetry snapshot.

## [0.3.6] - 2026-09-25

### Changed
- Feeding cards use the additives listed on the tent. Full Cycle and Mothers
  list CalMag+ at 2.5 ml/gal and Hydroguard at 2 ml/gal. Armor Si and a second
  CALiMAGic dose are not added unless those products are listed.

## [0.3.5] - 2026-09-25

### Changed
- Recirculating Flora feeding is quality-first for every tent. Vegetative is
  2.5 ml/gal of Micro, Gro, and Bloom, with Armor Si, CALiMAGic, and
  Hydroguard on each fill. The General Hydroponics late-veg 6 ml/gal row is
  not used; that mix measured about 2.2 mS/cm.
- Flower EC bands are 1.2–1.6 in early and mid flower and 1.0–1.4 in late
  flower, so a 2.2 mix is no longer treated as in range.

## [0.3.4] - 2026-09-01

### Changed
- Operator docs rewritten for HACS: Quick start with a 4×4 RDWC example,
  Cultivation Plan, upgrade notes, and copy-paste Lovelace/automation YAML.

## [0.3.3] - 2026-09-01

### Fixed
- Cultivation Plan no longer shows **Entity not found** after the Stage Started
  change. Stage Started and Week In Stage now reuse each grow space's existing
  id prefix (same as Growth Stage), and storage dashboards that still point at
  the old Week In Stage number are rewritten on reload.

## [0.3.2] - 2026-09-01

### Changed
- Cultivation Plan now uses a **Stage Started** date. Weeks in stage are
  computed from that date (and feed AI dosing and timeline math). Changing
  Growth Stage resets the date to today; you can still backdate it. Existing
  week numbers are converted on upgrade.
- AI Feeding Schedule markdown is expanded into a per-product mix-order list
  (Armor Si → CALiMAGic → Micro → Gro → Bloom → Hydroguard → pH) so the same
  readable card appears on every grow-space dashboard.

### Fixed
- AI health no longer treats live RDWC/DWC (Hydroguard / biologicals, or
  RDWC/DWC without a sterilant) as a sterile system. ORP ~200–300 mV is not
  flagged as critically low or as poor dissolved oxygen. Water at 65–68 °F is
  in-range (not an “upper limit”); concern starts at 72 °F. Vegetative VPD of
  0.7–1.2 kPa is acceptable. Current EC inside the GH week band is not
  diagnosed as underfeeding against a higher mix-to target.

## [0.3.1] - 2026-08-24

### Changed
- Prefer **LocalTuya** (then Tuya Local) as the water-metric source per grow
  space; Tuya cloud OpenAPI polling is fallback-only and is skipped while a
  local device is bound. New entries still default cloud polling off.
- Default Tuya cloud poll interval is now **600 seconds** (10 minutes) to
  stay within Tuya Trial IoT Core API quotas; existing entries keep their
  configured interval until Options are saved.

### Fixed
- Local water-monitor matching no longer crashes on Home Assistant 2026 device
  identifiers (3-tuples). Tuya Local probes that use long names such as
  "Total dissolved solids" / "Oxidation reduction potential" are classified
  even before units are available.

### Friendly Release Notes Template

Use this structure for each new release section to keep updates easy to scan:

- Start with a one-line plain-language summary.
- Add a short "Quick Start" list for HACS users when setup steps changed.
- List "What You Get" in simple feature bullets.
- Add "Important Notes" for prerequisites, caveats, or repairs.
- Keep technical validation short (`ruff`, `pytest`, OpenSpec when relevant).

Suggested headings:

- `Quick Start (HACS Users)`
- `What Is New`
- `Important Notes`
- `Services Added` (if any)
- `Validation`

## [0.3.0] - 2026-07-30

### Added
- Camera timelapse as an opt-in per-grow-space feature with configurable
  capture interval, frame retention, and optional capture-directory override.
- New timelapse capture pipeline with deterministic timestamped frame names,
  bounded retention pruning, and `/local/...` URL resolution for default
  `www`-backed storage.
- Per-entry scheduled capture runtime plus manual capture triggers via the new
  `Capture Timelapse Frame` button and `tendrilgrow.capture_timelapse_frame`
  service.
- New timelapse status sensors: frame count (with directory/latest-frame
  attributes) and latest-frame timestamp.
- New `tendrilgrow.build_timelapse` service that assembles frames to MP4 using
  Home Assistant's ffmpeg manager binary with async subprocess execution.

### Changed
- Timelapse scheduling now pauses automatically if capture fails due to a
  missing allow-list path and resumes once a capture succeeds.

### Fixed
- Added a dedicated Home Assistant Repair issue (`timelapse_not_allowlisted`)
  that explicitly identifies which capture path must be added to
  `allowlist_external_dirs`.
- Build-timelapse gracefully degrades when ffmpeg is unavailable by logging the
  equivalent manual command while preserving captured frames.

## [0.2.0] - 2026-07-30

### Added
- Dew point sensor derived from the mapped air temperature and humidity.
- Estimated Daily Light Integral (DLI) sensor from the mapped PPFD and the
  configured photoperiod (`mol/m²/day`).
- Estimated daily pump electricity-cost sensor, plus a new editable
  "Electricity Price" (per kWh) helper.
- Grow Timeline calendar entity exposing projected stage-end, harvest, and ready
  dates and the next reservoir flush due date.
- Home Assistant repair issues that flag when an AI provider is selected but no
  camera or model is configured.
- Grow Tasks to-do list that auto-generates actionable tasks (reservoir flush
  due, stage change approaching, and critical AI health alerts).
- AI Weekly Journal sensor summarizing the last 7 days of recorded AI health
  checks (count, average score, trend, and notable issues) as markdown.
- Actionable mobile notifications: flush-overdue and critical-AI alerts sent via
  a notify service now include action buttons ("Mark flushed" / "Run check")
  that call the matching service when tapped.

## [0.1.6] - 2026-07-30

### Fixed
- README logo now uses an absolute image URL so it renders in the HACS README
  viewer (which does not resolve repository-relative image paths).

## [0.1.5] - 2026-07-30

### Added
- Project brand icon and logo. Home Assistant 2026.3+ serves these local brand
  images (via the brand images proxy), so the TendrilGrow icon now appears in
  HACS and on the integration and device pages. Update to this release and
  restart Home Assistant to see it.
- Documentation site built with MkDocs Material at
  https://trec-torconsulting.github.io/TendrilGrow/.

## [0.1.4] - 2026-07-30

### Added
- Grow-type field now offers an `aeroponic` preset (e.g. a Clone King cloner)
  alongside `rdwc`, `dwc`, `soil`, `coco`, and `other`. The options/edit flow
  uses the same dropdown as the create flow, and custom values are still
  allowed, so any other method can be typed in.

## [0.1.3] - 2026-07-30

### Added
- Full lifecycle growth stages: `mother`, `clone`, `harvest`, `dry`, `cure`, and
  `ready` added to the growth-stage select (alongside seedling, vegetative,
  early/mid/late flower, and flush), with human-readable dropdown labels. The
  default stage remains `vegetative`.
- Stage-aware AI health objective: mother plants are assessed as permanent
  vegetative stock that are never flowered, clones on rooting, flowering stages
  on quality, and post-harvest stages (dry/cure) on drying/curing rather than
  reservoir chemistry. Added `mother` and `clone` reservoir targets.
- Per-grow-space stage-projection sensor (`sensor.<grow>_stage_projection`):
  days remaining in the current stage plus projected stage-end, harvest, and
  ready dates derived from the stage and week-in-stage (default stage durations
  verified against published grow timelines).
- `scripts/import_dashboard.py` to push a repo dashboard to a live Home
  Assistant (counterpart to `export_dashboard.py`), and a "Grow Timeline" card
  in the bundled `dashboards/tendrial_grow.yaml`.

## [0.1.2] - 2026-07-29

### Changed
- AI health entities (score, summary, feeding schedule, last check, critical
  alert, and the run button) are now attached to each grow-space device and
  named per grow space. Existing installs auto-migrate the legacy global ids
  (e.g. `sensor.ai_health_score` and `..._2`) to per-space ids
  (e.g. `sensor.<grow>_ai_health_score`) on setup; user-customized ids are
  left untouched. Update dashboards/automations that referenced the old ids
  (the bundled `dashboards/tendrial_grow.yaml` example is already updated).

## [0.1.1] - 2026-07-29

### Added
- Initial Home Assistant integration foundation
- Config/Options flow for one config entry per grow space
- Grow-space model with derived VPD metric support
- AI provider abstraction with model discovery for Gemini, OpenAI, Ollama
- Optional Tuya cloud water-monitoring: signed OpenAPI client, datapoint
  normalization (pH/EC/CF/ORP/TDS, temperature, humidity, battery), per-entry
  polling coordinator, per-device sensors, and automatic sensor-role mapping
- Distinct water-quality sensor roles (pH, EC, CF, ORP, TDS) with legacy
  `ec_tds` migration to `tds`
- Distinct **air** (canopy) `temperature`/`humidity` roles and a separate
  `water_temperature` role; Tuya water temperature now maps to
  `water_temperature` instead of the air role
- Unit-aware VPD (°F→°C) computed from air temperature + air humidity and
  exposed as a per-grow-space VPD sensor; air temp/humidity are mappable even
  when Tuya is enabled
- Camera-based AI grow-health checks: quality-first agronomy prompt, scoring,
  observations, issues, recommended actions, and a dynamic feeding schedule
- Vision report generation for Gemini, OpenAI, and Ollama
- Scheduled and on-demand health checks with persistent history and retention
- Critical-score notifications (persistent notification plus optional notify
  service)
- Pump control and monitoring: map and toggle RDWC, chiller, and air pumps via
  dashboard switches or automation services; real-time per-pump and total power
  consumption tracking; RDWC pump integration for safe header-bucket dosing
  workflow; optional explicit power sensor mapping or automatic discovery via
  device registry
- Reservoir flush tracking: a per-grow-space "Flush Now" button and `mark_flush`
  service record each full flush; an editable flush interval (default 7 days)
  drives days-since, days-until, next-due, and last-flush sensors plus a
  problem-class "flush due" binary sensor; a de-duplicated persistent (and
  optional notify-service) reminder fires when a flush is overdue; flush status
  is surfaced to the AI advisor's cultivation context. Manual recording only
  — no actuation.
- Cultivation-context helper entities (growth stage, strain, targets, reservoir
  volume, nutrients) that ground AI advice
- AI health entities (score, summary, feeding schedule, last check, critical
  alert) and a run button
- Services: `run_ai_health_check` and `rebuild_automap`
- Diagnostics redaction for secrets (AI keys and Tuya access secret)
- CI workflows for hassfest, HACS validation, lint and tests

### Planned
- Bundled Lovelace dashboard cards
- Safety-first automations engine (opt-in control actuation)
- Additional AI providers (Anthropic, Azure OpenAI, OpenAI-compatible)
