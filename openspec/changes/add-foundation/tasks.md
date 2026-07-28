# Tasks: add-foundation

## 1. Repository & packaging

- [x] 1.1 Create repo structure: `custom_components/tendrilgrow/`, `tests/`, `README.md`, `LICENSE`, `.gitignore`
- [x] 1.2 Add `hacs.json` (name, integration, HA min version) for HACS custom-integration install
- [x] 1.3 Add `custom_components/tendrilgrow/manifest.json` (domain `tendrilgrow`, name, version, docs/issue URLs, codeowners, `config_flow: true`, iot_class, integration_type)
- [x] 1.4 Add `const.py` with `DOMAIN`, config keys, and role identifiers
- [x] 1.5 Add dev tooling: `requirements-test.txt`, `ruff`/`black` config, and `pytest` config

## 2. Integration foundation

- [x] 2.1 Implement async `async_setup_entry` / `async_unload_entry` in `__init__.py` (one config entry per grow space)
- [x] 2.2 Store runtime data on the config entry and register an update listener for reload-on-options
- [x] 2.3 Add a `tendrilgrow` logger and ensure secrets (AI keys) are never logged
- [x] 2.4 Add `diagnostics.py` that redacts provider credentials
- [x] 2.5 Verify per-entry setup/unload/reload lifecycle with a smoke test (other entries unaffected)

## 3. Grow data model

- [x] 3.1 Define `GrowSpace` model (name, grow type, size/descriptor, sites, mappings, targets, schedules)
- [x] 3.2 Define extensible sensor-role and control-role registries bound to entity ids
- [x] 3.3 Implement zone/site representation within a grow space
- [x] 3.4 Implement derived metrics with VPD from temp+humidity; report unavailable on missing inputs
- [x] 3.5 Implement (de)serialization to/from config-entry data with stable space ids
- [x] 3.6 Unit tests for the model, role binding, and VPD calculation

## 4. Config & options flow

- [x] 4.1 Implement config flow: create a grow space (name + grow type) as one config entry, with unique-name guard
- [x] 4.2 Add entity-selector steps to map sensor/control roles (optional roles allowed)
- [x] 4.3 Implement options flow to edit a grow space's mappings and per-space settings
- [x] 4.4 Trigger reload on options change and apply new config (per-entry, others unaffected)
- [x] 4.5 Add `strings.json` and `translations/en.json` for flow steps and errors
- [x] 4.6 Tests for create, duplicate rejection, optional-role skip, edit, and per-entry remove

## 5. AI provider abstraction

- [x] 5.1 Define `AIProvider` interface (capabilities + config schema + list-models)
- [x] 5.2 Register providers: Gemini, Ollama, OpenAI (selection + config metadata)
- [x] 5.3 Add provider selection and per-provider credential/endpoint steps to config UI
- [x] 5.4 Validate provider settings (required key present / endpoint format) with actionable errors
- [x] 5.5 Implement dynamic model discovery after credentials; present model picker with retry/manual fallback
- [x] 5.6 Store credentials securely and confirm redaction in logs/diagnostics
- [x] 5.7 Ensure grow-advice/vision features stay disabled (only model discovery calls allowed)
- [x] 5.8 Tests for selection, validation failure, model discovery, discovery-failure fallback, and secret redaction

## 6. CI & validation

- [x] 6.1 Add GitHub Actions workflow running `hassfest`
- [x] 6.2 Add HACS validation action workflow
- [x] 6.3 Add lint + `pytest` workflow
- [ ] 6.4 Validate the model and flows against the maintainer's live grow data (2 RDWC Vivosun tents)
- [x] 6.5 Update README with install steps, required companion integrations (Vivosun HACS, Tuya HACS, camera), and configuration guide

## 7. Spec upkeep

- [x] 7.1 Update OpenSpec artifacts to reflect any scope or decision changes discovered during implementation
