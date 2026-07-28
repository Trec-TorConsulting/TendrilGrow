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
- Extensible role mappings (temperature, humidity/VPD, light, pH, EC, CF,
	ORP, TDS, cameras, lights, fans, inline fans)
- Derived metric support (VPD)
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

Planned in future changes:
- Live grow-advice execution
- Vision/image review workflows
- Rich Lovelace dashboard cards
- Automation orchestration engine

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
- `custom_components/tendrilgrow/ai/providers.py`
	- Provider abstraction and model discovery endpoints
- `custom_components/tendrilgrow/diagnostics.py`
	- Redacted diagnostics payloads for supportability

## Installation via HACS

### Prerequisites

- Home Assistant with HACS installed
- Companion integrations already configured if you use them:
	- Vivosun HACS integration (controllers)
	- Tuya HACS integration (water monitors)
	- Camera integration (for future vision features)

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
2. Map sensor and control entities (optional mappings supported).
3. Pick AI provider (`None`, `Gemini`, `OpenAI`, or `Ollama`).
4. Enter provider credentials/endpoint.
5. Select discovered model or use manual model fallback if discovery fails.

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
