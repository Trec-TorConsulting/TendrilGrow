# Proposal: add-dashboard-cards

## Why

TendrilGrow already produces rich per-grow-space data — AI health scores,
summaries, feeding schedules, water-quality metrics, and cultivation context — but
users must hand-build Lovelace views to see it. Bundled dashboard cards give an
at-a-glance grow cockpit and make the AI advisor usable without YAML wrangling.
This is a **new, not-yet-built** capability.

## What Changes

- Add a **custom Lovelace card bundle** (Lit + TypeScript) built to a single
  JavaScript file and **served by the integration** (registered as a frontend
  resource) so no manual resource setup is needed.
- Add **`tendrilgrow-grow-card`**: the primary grow-space cockpit card showing the
  AI health **score** (color-coded by severity), last-check time, summary, latest
  observations/issues/recommended actions, the **feeding schedule**, key water
  metrics (pH, EC, CF, TDS, ORP, water temp), VPD, a **critical-alert** indicator,
  and a **Run AI Health Check** action.
- Add **`tendrilgrow-ai-report-card`**: a detailed AI report view with confidence
  and rationale, full observations/issues/actions/feeding schedule, and
  **history navigation** across retained results.
- Add **GUI card editors** for both cards (device/entity pickers) and register
  them in the Lovelace **card picker** (`window.customCards`).
- Add a **shared grow-space device** for the AI-health entities so all of a space's
  entities (Tuya metrics, context helpers, AI health) group under one device and a
  card can bind to a single `device_id`.
- Add a **documented example YAML dashboard** (built-in cards only) as a no-build
  fallback and reference layout.

## Capabilities

### New Capabilities
- `dashboard-cards`: Bundled, integration-served Lovelace cards (grow cockpit + AI
  report) with GUI editors, card-picker registration, graceful degradation, and a
  documented example dashboard.

### Modified Capabilities
- `ai-health-monitoring`: AI-health entities SHALL attach to the shared grow-space
  device so a card can resolve all of a space's entities from one `device_id`
  (unique ids unchanged).

## Impact

- **New code**: `frontend/` TypeScript sources; a bundler config (Rollup or
  esbuild); build output at `custom_components/tendrilgrow/frontend/tendrilgrow-cards.js`;
  static-path + `add_extra_js_url` registration in `__init__.py`; shared
  `grow_device_info` applied to AI-health entities in `sensor.py`,
  `binary_sensor.py`, `button.py`.
- **Packaging**: `frontend/package.json` (+ lockfile), a `build:frontend` script,
  the built bundle committed (HACS installs from source, no build step at install),
  and a CI job that builds the bundle and fails if it is stale.
- **Docs**: README dashboard section + `docs/dashboard-example.yaml`.
- **No breaking changes**: entity unique ids and the config/options flow are
  unchanged; cards are additive.
- **Dependencies**: dev-only Node toolchain (`lit`, bundler, TypeScript). No new
  Python runtime dependencies.
