# Design: add-dashboard-cards

## Context

The integration exposes per-grow-space entities but no packaged UI. This change
adds custom Lovelace cards, built from TypeScript, bundled to one JS file, and
served by the integration so users get a working grow dashboard immediately. A
cheaper implementation model should be able to follow this design step by step.

Constraints:
- HACS installs from source; there is **no build step at install time**, so the
  built bundle MUST be committed to the repo and kept in sync via CI.
- Cards must degrade gracefully when entities are missing/unavailable.
- No new Python runtime dependencies; the Node toolchain is dev/CI only.
- Follow Home Assistant custom-card conventions (`setConfig`, `hass` setter,
  `getCardSize`, `getConfigElement`, `getStubConfig`, `window.customCards`).

## Entity data contract (source of truth for the cards)

All entities are created per grow-space config entry. Unique-id suffixes (prefix
is `<entry_id>_`):

- `ai_health_score` → `sensor`; state = integer score 0–100 or unknown.
  Attributes: `severity`, `summary`, `report` (markdown), `observations` (list),
  `issues` (list), `recommended_actions` (list), `feeding_schedule` (list),
  `feeding_schedule_md` (markdown), `confidence`, `confidence_rationale`,
  `provider`, `model`, `reason`, `history_count`, `running`, `last_error`.
- `ai_health_summary` → `sensor`; state = short summary text.
- `ai_feeding_schedule` → `sensor`; state = short status; same feeding attributes.
- `ai_health_last_check` → `sensor` (timestamp device class).
- `ai_health_critical_alert` → `binary_sensor` (device_class problem).
- `run_ai_health_check` → `button`.
- Tuya metrics → `sensor` unique ids `<entry_id>_<device_id>_<metric>` where metric
  ∈ {ph, ec, cf, tds, orp, water_temp_c, ambient_humidity, battery_pct}.
- Context → `select` (`ctx_stage`), `number` (`ctx_*`), `text` (`ctx_*`).

The cards resolve entities from a single `device_id` (preferred) via
`hass.entities`/`hass.devices`, or from explicit entity ids in card config.

## Goals / Non-Goals

**Goals:**
- One primary "grow cockpit" card and one detailed "AI report" card.
- GUI editors and card-picker registration.
- Integration-served bundle; zero manual resource registration.
- Graceful degradation and a documented no-build YAML dashboard.

**Non-Goals:**
- Historical charts/graphs beyond HA's built-in history (future analytics change).
- Editing cultivation context from the card (users edit the helper entities).
- Mobile-specific layouts beyond responsive CSS.

## Decisions

### Custom Lit cards, single committed bundle
Source in `frontend/src/*.ts`; bundle to
`custom_components/tendrilgrow/frontend/tendrilgrow-cards.js` with Rollup
(`@rollup/plugin-node-resolve`, `@rollup/plugin-typescript`, `rollup-plugin-terser`).
The bundle is committed. Rationale: HACS serves source directly; committing the
built asset avoids requiring Node at install time.

### Integration serves the bundle
In `async_setup` (once, not per entry): register a static path and add the JS URL:
```python
from homeassistant.components.http import StaticPathConfig
from homeassistant.components import frontend

URL = "/tendrilgrow/tendrilgrow-cards.js"
PATH = hass.config.path("custom_components/tendrilgrow/frontend/tendrilgrow-cards.js")
await hass.http.async_register_static_paths([StaticPathConfig(URL, PATH, False)])
frontend.add_extra_js_url(hass, URL)
```
Rationale: users get cards without manually adding Lovelace resources. Register
idempotently and guard with a `hass.data` flag.

### File layout
```
frontend/
  package.json            # deps + build:frontend script
  tsconfig.json
  rollup.config.mjs
  src/
    main.ts               # registers customElements + window.customCards
    grow-card.ts          # tendrilgrow-grow-card
    grow-card-editor.ts   # tendrilgrow-grow-card-editor
    ai-report-card.ts     # tendrilgrow-ai-report-card
    ai-report-card-editor.ts
    entity-resolver.ts    # device_id -> entity ids; safe state/attr getters
    types.ts              # HomeAssistant/LovelaceCard typings (minimal)
    styles.ts             # shared CSS
custom_components/tendrilgrow/frontend/tendrilgrow-cards.js  # committed build output
docs/dashboard-example.yaml
```

### Card behavior
- `tendrilgrow-grow-card` config: `{ type, device_id?, entity?, name?, show_actions? }`.
  Renders: header (name), score badge/gauge colored by severity
  (low=green, medium=amber, high=orange, critical=red; unknown=grey), last-check
  relative time, summary, collapsible observations/issues/recommended actions,
  feeding schedule (from `feeding_schedule` list), water metrics row (only metrics
  that exist), VPD if a `sensor.*` VPD/derived value is available, a critical-alert
  chip when the binary sensor is on, and a "Run AI Health Check" button that calls
  `button.press` on the run button (fallback: `tendrilgrow.run_ai_health_check`
  with `entry_id`). While `running` is true, show a spinner and disable the button.
- `tendrilgrow-ai-report-card` config: `{ type, device_id?, entity? }`. Renders the
  full latest report using the `report`/`feeding_schedule_md` markdown attributes,
  confidence + rationale, provider/model, and prev/next history navigation using
  `history_count` (history entries are read from the score sensor attributes; if
  only the latest is exposed, disable navigation gracefully).

### GUI editors + picker
Each editor implements `setConfig`/`configChanged` with a `ha-device-picker` (or
`ha-entity-picker`). `main.ts` sets `window.customCards`:
```js
window.customCards.push({
  type: "tendrilgrow-grow-card",
  name: "TendrilGrow Grow Card",
  description: "AI grow-health cockpit for one grow space",
  preview: true,
  documentationURL: "https://github.com/Trec-TorConsulting/TendrilGrow",
});
```

### Shared grow-space device
Add `entity.py: grow_device_info(entry)` usage to the AI-health entities so they
share the same `identifiers={("tendrilgrow", entry.entry_id)}` device as context
helpers. Keep unique ids unchanged so no entities are recreated. Rationale: lets a
card bind to one `device_id`.

### Stale-bundle CI guard
A CI job runs `npm ci && npm run build:frontend` in `frontend/` and fails if
`git diff --exit-code custom_components/tendrilgrow/frontend/tendrilgrow-cards.js`
shows drift. Rationale: guarantees the committed bundle matches source.

## Risks / Trade-offs

- **Committed build artifact can drift** → CI stale-bundle guard.
- **HA frontend API changes** (static path helper) → wrap registration in
  try/except and log; cards still load if the user adds the resource manually.
- **Device binding when entities lack a device** → the shared-device task fixes
  this; editors also allow explicit entity selection as a fallback.
- **Cheaper model unfamiliar with Lit** → design pins exact files, lifecycle
  methods, and an entity contract; tasks are ordered and independently testable.

## Acceptance criteria

- Fresh install shows both cards in the card picker with working previews.
- `tendrilgrow-grow-card` renders score, summary, feeding schedule, and available
  water metrics for a configured grow space, and the Run button triggers a check.
- Missing/unknown entities render placeholders, not errors.
- `npm run build:frontend` reproduces the committed bundle byte-for-byte in CI.
- README documents cards; `docs/dashboard-example.yaml` loads with built-in cards.

## Migration Plan

Additive. Existing installs gain cards after update + restart. The shared-device
change relinks existing AI-health entities to the grow-space device without
changing unique ids (no entity loss). Rollback: remove the frontend registration
and cards; entities and flows are unaffected.
