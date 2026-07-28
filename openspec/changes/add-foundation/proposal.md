# Proposal: add-foundation

## Why

TendrilGrow bundles a Home Assistant integration, dashboards, an AI grow advisor,
and automations into a single HACS-installable package for indoor cultivation.
Before any feature work, the project needs a validated foundation: a HACS-compliant
custom integration skeleton, a flexible grow-space data model, and a user-driven
configuration flow — grounded in the maintainer's live setup (2 RDWC Vivosun tents)
but designed so any user's sensors, controls, grow types, and spaces fit.

## What Changes

- Create the `custom_components/tendrilgrow/` integration skeleton (manifest,
  domain, async setup/unload, config entry lifecycle) that passes `hassfest` and
  HACS validation.
- Add repository packaging for HACS: `hacs.json`, repo metadata, and validation
  workflow so the integration is installable via HACS.
- Introduce a **config flow + options flow** that lets a user create and edit
  **grow spaces** as **one config entry per grow space**, each mapping its own HA
  entities (no hardcoded entity ids) and owning its own equipment and settings.
- Define a **flexible grow-space data model** (space → zones/sites → mapped
  sensors/controls, grow type, targets/schedules) that supports RDWC and other grow
  types, and varying tent/room sizes.
- Add a **pluggable AI provider abstraction** (interface + provider selection and
  credential/endpoint config) so users can choose Gemini, Ollama, OpenAI, etc.
  After credentials are entered, the flow **fetches the provider's available models**
  for the user to select. Foundation ships the interface, configuration, and model
  discovery only — grow advice and vision reviews arrive in a later change.
- Establish project conventions: repo structure, quality-scale target, translations
  scaffolding, logging, tests, and CI (hassfest + HACS action + lint).

Non-goals for this change (deferred to later proposals): the Lovelace dashboard
cards, live AI advice/vision reviews, and the automations engine.

## Capabilities

### New Capabilities
- `integration-foundation`: HACS-compliant custom integration skeleton — manifest,
  domain constants, async setup/unload, config-entry lifecycle, and passing
  hassfest/HACS validation.
- `grow-space-config`: Config flow and options flow for creating/editing grow
  spaces as one config entry per space, with user-mapped entities and per-space settings.
- `grow-data-model`: Flexible domain model for grow spaces, zones/sites, mapped
  sensors and controls, grow type, and targets/schedules.
- `ai-provider-abstraction`: Pluggable AI provider interface with user-selectable
  provider, per-provider credential/endpoint configuration, and dynamic discovery
  of the provider's available models (no grow-advice/vision calls yet).

### Modified Capabilities
<!-- None — this is the first change; no existing specs. -->

## Impact

- **New code**: `custom_components/tendrilgrow/` (manifest.json, const.py,
  __init__.py, config_flow.py, models/data model, ai/provider interface,
  translations, tests).
- **Repo/packaging**: `hacs.json`, `README`, `.github/workflows` for hassfest,
  HACS validation, and lint.
- **Dependencies**: Home Assistant core APIs; no third-party AI SDKs pinned in the
  foundation (added per-provider in a later change). Model discovery uses each
  provider's list-models endpoint via generic HTTP where possible.
- **Config/UX**: One config entry per grow space; grow spaces managed via UI flows.
- **Companion integrations** (user-provided entities): Vivosun HACS integration for
  the E42a+ controllers and Tuya HACS integration for the RDWC header-bucket water
  monitors — TendrilGrow maps their entities, it does not replace them.
- **Validation source**: Maintainer's live HA (2 RDWC Vivosun tents, Reolink
  cameras, temp/humidity, PPFD/lux, pH/EC/TDS) used to verify the model fits real data.

## Resolved Decisions

- Target the latest Home Assistant release and the latest Python it supports.
- One config entry per grow space (each space owns its equipment and settings).
- Vivosun controls come from the Vivosun HACS integration; RDWC water monitors from
  the Tuya HACS integration — foundation maps these entities only.
- Integration domain slug: `tendrilgrow`.
- Initial AI providers: Gemini, Ollama, OpenAI — with dynamic model listing after
  credentials are entered.
