# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and semantic versioning.

## [Unreleased]

### Changed
- Default Tuya cloud poll interval is now **600 seconds** (10 minutes) to
  stay within Tuya Trial IoT Core API quotas; existing entries keep their
  configured interval until Options are saved.

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
