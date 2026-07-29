# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and semantic versioning.

## [Unreleased]

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
