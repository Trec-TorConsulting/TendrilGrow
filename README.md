# TendrilGrow

TendrilGrow is a Home Assistant custom integration for indoor cultivation
workflows. It unifies grow-space configuration, sensor/control mapping, and
AI-provider model selection into a single HACS-installable package.

## Status

- Maturity: Foundation release (MVP integration scaffolding)
- Distribution: HACS custom integration
- Config model: One Home Assistant config entry per grow space
- License: MIT

## Core capabilities

- One grow-space config entry per tent/room/zone
- Flexible grow-space model: sites, mapped sensors, mapped controls, targets,
	schedules
- Extensible role mappings: **air** temperature/humidity (canopy, for VPD), a
	distinct water/reservoir temperature, light, pH, EC, CF, ORP, TDS, cameras,
	lights, fans, inline fans
- **Pump control and monitoring** (RDWC, chiller, air pumps):
	- Toggle pumps on/off via dashboard switches or automation services
	- Real-time power consumption monitoring per pump and total
	- RDWC pump integration for safe header-bucket dosing workflow
	- Optional explicit power sensor mapping or automatic sensor discovery
- **Reservoir flush tracking** (7-10 day RDWC cadence):
	- One-press "Flush Now" button records each full flush/refill
	- Editable per-space flush interval and days-since / days-until / next-due sensors
	- Overdue "flush due" indicator with a de-duplicated reminder notification
	- Flush status folded into the AI advisor's cultivation context
- Unit-aware derived VPD (°F→°C) exposed as a per-grow-space VPD sensor,
	computed from the mapped air temperature and air humidity
- Optional Tuya cloud water-monitoring: signed OpenAPI polling, datapoint
	normalization, per-device sensors, and automatic sensor-role mapping
- Camera-based AI health checks: quality-first agronomy scoring, observations,
	issues, recommended actions, and a dynamic feeding schedule
- Scheduled and on-demand checks with persistent history and retention
- Critical-score notifications (persistent notification plus optional notify service)
- Editable cultivation-context helpers (growth stage, strain, targets,
	reservoir volume, nutrients) that ground AI advice
- Full lifecycle growth stages (seedling, mother, clone, vegetative,
	early/mid/late flower, flush, harvest, dry, cure, ready) with stage-aware AI
	objectives (mothers judged on health/structure, clones on rooting, flowering
	on quality, dry/cure on drying) plus a per-space stage-projection sensor
	(days remaining and projected stage-end/harvest/ready dates)
- AI health entities (score, summary, feeding schedule, last check, critical
	alert) and a run button
- Services: `run_ai_health_check` and `rebuild_automap`
- Pluggable AI provider selection:
	- Google Gemini
	- OpenAI
	- Ollama
- Dynamic model discovery after provider credentials are entered
- Secrets-safe diagnostics and logging (API keys are redacted)

## Current scope and non-goals

Included now:
- Integration foundation, config flow, options flow, model abstraction,
	governance and CI
- Tuya cloud water-monitoring with normalized water-quality sensors
- Camera-based AI grow-health checks, scoring, and dynamic feeding schedules
- Cultivation-context helper entities and AI health entities/services
- Pump control and monitoring: RDWC, chiller, and air pump switches with
	dashboard control and real-time power consumption tracking
- Reservoir flush tracking: record button, interval, status sensors, overdue
	reminder, and AI-context awareness for the 7-10 day RDWC flush cadence

Planned in future changes:
- Bundled Lovelace dashboard cards
- Automation orchestration engine (safety-first, opt-in control actuation)
- Additional AI providers (Anthropic, Azure OpenAI, OpenAI-compatible)

## Architecture overview

Main runtime modules:

- `custom_components/tendrilgrow/__init__.py`
	- Config entry lifecycle (setup/unload/reload)
	- Per-entry runtime data
- `custom_components/tendrilgrow/config_flow.py`
	- Onboarding flow and options flow
	- Entity mapping, provider selection, credential handling, model selection
- `custom_components/tendrilgrow/models/grow.py`
	- Grow-space domain model, serialization, VPD computation
- `custom_components/tendrilgrow/coordinator.py`
	- Per-entry Tuya cloud polling coordinator
- `custom_components/tendrilgrow/tuya_client.py`
	- Signed Tuya OpenAPI client and datapoint normalization
- `custom_components/tendrilgrow/ai/providers.py`
	- Provider abstraction, model discovery, and vision report generation
- `custom_components/tendrilgrow/ai/health_checks.py`
	- Camera-based health-check runtime, prompt, scoring, persistence, notifications
- `custom_components/tendrilgrow/{sensor,binary_sensor,button,number,select,text}.py`
	- Tuya metric sensors, AI health entities, and cultivation-context helpers
- `custom_components/tendrilgrow/diagnostics.py`
	- Redacted diagnostics payloads for supportability

## Installation via HACS

### Prerequisites

- Home Assistant with HACS installed
- Companion integrations already configured if you use them:
	- Vivosun HACS integration (controllers)
	- Tuya HACS integration (water monitors)
	- Camera integration (required for AI vision health checks)

### Install steps

1. Open HACS in Home Assistant.
2. Navigate to menu -> Custom repositories.
3. Add this GitHub repository URL.
4. Select category: `Integration`.
5. Install `TendrilGrow` from HACS.
6. Restart Home Assistant.
7. Go to Settings -> Devices & Services -> Add Integration.
8. Add `TendrilGrow`.

During install in HACS, you will see behavior similar to:

- `TendrilGrow`
- `Commit <sha> will be downloaded`
- Installed path: `/config/custom_components/tendrilgrow`

Home Assistant restart is required after downloading custom integrations.
Changes in `custom_components` are not applied until restart.

### First-time setup flow

For each grow space (one entry per space):

1. Enter grow-space name and type.
2. Map sensor and control entities (optional mappings supported). Optionally
	enable Tuya cloud polling and enter Tuya credentials and device IDs; when
	enabled, water-quality sensors are provided and mapped automatically.
3. Set AI health options (check interval, critical-score threshold, optional
	notify service, result retention).
4. Pick AI provider (`None`, `Gemini`, `OpenAI`, or `Ollama`).
5. Enter provider credentials/endpoint.
6. Select discovered model or use manual model fallback if discovery fails.

To run AI health checks, map a `camera` entity and select a vision-capable
provider and model. Checks run on a schedule, on demand via the run button, or
through the `tendrilgrow.run_ai_health_check` service.

## Dashboards

An example multi-tab Lovelace dashboard is tracked at
[dashboards/tendrial_grow.yaml](dashboards/tendrial_grow.yaml): an executive
overview plus a per-zone tab, with camera snapshots, reservoir chemistry,
trends, AI health, the cultivation plan, and a **Reservoir Flush** card (the
Flush Now button, flush interval, days-since / days-until / next-due, and the
flush-due alert).

Entity ids in the file are specific to the maintainer's grow spaces
(`3x3_mothers_tent_*`, `4x4_full_cycle_tent_*`); adjust the prefixes for your own
spaces.

- Reuse it: open the dashboard's **Raw configuration editor** in Home Assistant
	and paste the file contents, or add individual cards via **Add card → Manual**.
- Re-export a live dashboard into the repo:
	`./.venv/bin/python scripts/export_dashboard.py <url_path>` — reads read-only
	`HA_URL`/`HA_TOKEN` from `.env`; the token is never printed or logged.
- Push a repo dashboard back to the live server:
	`./.venv/bin/python scripts/import_dashboard.py <url_path>` — dry-run by
	default (add `--apply` to save). It backs up the live config first, warns on
	any referenced entity ids that don't exist, and never prints the token.

## Configuration model

Each grow-space entry stores:

- Identity and grow descriptors
- Site definitions
- Sensor and control role mappings
- Targets and schedules
- AI provider, credential references, selected model

No hardcoded entity IDs are required.

## Security and secrets

- Credentials are treated as sensitive data.
- API keys are redacted in diagnostics.
- Avoid posting real keys or internal endpoint details in issues.
- See `SECURITY.md` for reporting process.

## Quality gates

CI workflows include:

- Home Assistant `hassfest`
- HACS validation action
- Ruff lint and pytest

## Local development

### Quick start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements-test.txt
./.venv/bin/ruff check .
./.venv/bin/pytest -q
```

### Local manual install into Home Assistant

Copy `custom_components/tendrilgrow` into your Home Assistant config at:

`/config/custom_components/tendrilgrow`

Then restart Home Assistant and add the integration from Devices & Services.

## Operations and support

- Usage/support: See `SUPPORT.md`
- Security reporting: See `SECURITY.md`
- Contribution guide: See `CONTRIBUTING.md`
- Community standards: See `CODE_OF_CONDUCT.md`

## Disclaimer

TendrilGrow assists monitoring and decision support. It does not replace safe
electrical, environmental, or horticultural practices. Validate automations and
control actions before production use.
