# Tasks: add-dashboard-cards

> Forward-looking change — **not yet implemented**. Work top to bottom; each task
> is independently verifiable. Do not check a box until its verification passes.

## 1. Frontend toolchain

- [ ] 1.1 Create `frontend/package.json` with deps `lit`, devDeps `typescript`, `rollup`, `@rollup/plugin-node-resolve`, `@rollup/plugin-typescript`, `rollup-plugin-terser`, and a `build:frontend` script that outputs `../custom_components/tendrilgrow/frontend/tendrilgrow-cards.js`
- [ ] 1.2 Add `frontend/tsconfig.json` (target ES2021, `experimentalDecorators`, `useDefineForClassFields: false`, `moduleResolution: node`)
- [ ] 1.3 Add `frontend/rollup.config.mjs` producing a single minified IIFE/ES bundle
- [ ] 1.4 Add `frontend/src/types.ts` with minimal `HomeAssistant`, `LovelaceCard`, `LovelaceCardEditor` typings
- [ ] 1.5 Verify: `cd frontend && npm ci && npm run build:frontend` produces the bundle with no type errors

## 2. Shared grow-space device (prep)

- [ ] 2.1 Apply `grow_device_info(entry)` to `AIHealthBaseSensor` (`sensor.py`), the alert binary sensor (`binary_sensor.py`), and the run button (`button.py`) — keep all `unique_id`s unchanged
- [ ] 2.2 Verify in a test that AI-health, Tuya, and context entities for one entry share one device (`identifiers={("tendrilgrow", entry_id)}`) and that unique ids are unchanged (`tests/test_dashboard_device.py`)

## 3. Entity resolver + shared utilities

- [ ] 3.1 Add `frontend/src/entity-resolver.ts`: given `hass` + `device_id`, return the grow space's entity ids by unique-id suffix; provide safe `getState`/`getAttr` helpers that tolerate missing/unknown/unavailable
- [ ] 3.2 Add `frontend/src/styles.ts` with shared CSS (severity color map: low/medium/high/critical/unknown)
- [ ] 3.3 Unit-test the resolver with a mocked `hass` (missing entity → null, not throw)

## 4. Grow cockpit card

- [ ] 4.1 Implement `frontend/src/grow-card.ts` (`tendrilgrow-grow-card`): `setConfig`, `hass` setter, `getCardSize`, render score badge (color by `severity`), last-check relative time, summary, collapsible observations/issues/recommended actions, feeding schedule list, water-metrics row (render only metrics present), critical-alert chip when the binary sensor is on
- [ ] 4.2 Implement the Run action: press the `run_ai_health_check` button entity, falling back to the `tendrilgrow.run_ai_health_check` service with `entry_id`; disable + spinner while `running` attribute is true
- [ ] 4.3 Graceful degradation: no result / unknown score / unavailable metric renders placeholders, never throws
- [ ] 4.4 Implement `getStubConfig` returning a sensible default (first TendrilGrow device)

## 5. AI report card

- [ ] 5.1 Implement `frontend/src/ai-report-card.ts` (`tendrilgrow-ai-report-card`): render `report` and `feeding_schedule_md` markdown, confidence + `confidence_rationale`, provider/model
- [ ] 5.2 Implement history navigation using `history_count`; disable prev/next when only one result is available
- [ ] 5.3 Graceful degradation for missing report/history

## 6. Editors + registration

- [ ] 6.1 Implement `grow-card-editor.ts` and `ai-report-card-editor.ts` with a `ha-device-picker` (fallback `ha-entity-picker`), emitting `config-changed`
- [ ] 6.2 Implement `frontend/src/main.ts`: define all custom elements and push both cards to `window.customCards` (name, description, `preview: true`, documentationURL)
- [ ] 6.3 Rebuild the bundle and verify both cards appear in the card picker with working previews in a running HA

## 7. Serve the bundle from the integration

- [ ] 7.1 In `__init__.py async_setup` (once, guarded by a `hass.data` flag), register the static path `/tendrilgrow/tendrilgrow-cards.js` → built bundle and call `frontend.add_extra_js_url`
- [ ] 7.2 Wrap registration in try/except; log at warning and continue if it fails (non-fatal)
- [ ] 7.3 Verify the URL serves the bundle and the cards load without any manual Lovelace resource

## 8. Example dashboard + docs

- [ ] 8.1 Add `docs/dashboard-example.yaml` using only built-in cards (gauge for score, markdown for `report`/`feeding_schedule_md`, entities for water metrics + context)
- [ ] 8.2 Add a README "Dashboards" section covering the auto-installed custom cards and the YAML fallback

## 9. CI + validation

- [ ] 9.1 Add a CI job: `cd frontend && npm ci && npm run build:frontend && git diff --exit-code custom_components/tendrilgrow/frontend/tendrilgrow-cards.js` (fails on stale bundle)
- [ ] 9.2 Ensure `hassfest`/HACS validation still pass with the served static path
- [ ] 9.3 Commit the built bundle; confirm a clean checkout renders cards without Node
