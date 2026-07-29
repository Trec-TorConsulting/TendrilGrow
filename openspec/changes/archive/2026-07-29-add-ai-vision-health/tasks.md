# Tasks: add-ai-vision-health

> Retroactive change. All tasks are **complete** — they document code already
> shipped in `custom_components/tendrilgrow/`. Checkboxes reflect implemented and
> tested behavior.

## 1. Provider vision execution

- [x] 1.1 Add `generate_vision_health_report` for Gemini/OpenAI/Ollama (`ai/providers.py`)
- [x] 1.2 Base64-encode the image and post to each provider's multimodal endpoint
- [x] 1.3 Extract text from each provider response; raise `ProviderExecutionError` on failure
- [x] 1.4 Remove the foundation "no vision" scope limit (superseded)

## 2. Health-check runtime

- [x] 2.1 Enforce preconditions (provider+model and mapped camera) before any call
- [x] 2.2 Capture camera snapshot with proxy fallback (`_async_get_camera_snapshot`)
- [x] 2.3 Collect mapped metric states and operator cultivation context
- [x] 2.4 Build the quality-first agronomy prompt with per-stage `STAGE_TARGETS`
- [x] 2.5 Parse strict JSON into `AIHealthResult`; tolerate non-JSON with an "unknown" result
- [x] 2.6 Clamp score/confidence to 0–100

## 3. Persistence, entities, notifications

- [x] 3.1 Persist history via HA `Store`; trim to retention window each run
- [x] 3.2 Dispatch updates to entities; ephemeral store fallback for tests
- [x] 3.3 Add score, summary, feeding-schedule, and last-check sensors (`sensor.py`)
- [x] 3.4 Add critical-alert binary sensor (`binary_sensor.py`) and run button (`button.py`)
- [x] 3.5 Persistent notification + optional notify service on critical score

## 4. Scheduling, service, config

- [x] 4.1 Schedule periodic checks and one delayed startup check (`__init__.py`)
- [x] 4.2 Register `run_ai_health_check` service for one/all entries (`services.yaml`)
- [x] 4.3 Add AI-health settings to config/options flows (interval, threshold, notify, retention)
- [x] 4.4 Keep provider keys redacted; include AI health state in diagnostics

## 5. Tests

- [x] 5.1 Prompt build includes context and metrics (`tests/test_health_checks.py`)
- [x] 5.2 Result parsing for rich JSON, non-JSON fallback, and round-trip
