# Proposal: add-ai-vision-health

## Why

Growers need early warning when a canopy shows stress that raw telemetry alone
misses. A camera snapshot analyzed by a multimodal model, combined with reservoir
and environment metrics plus cultivation context, produces an actionable health
score, issue list, and a dynamic feeding plan. This capability is **already
shipped**; this change documents it retroactively and lifts the foundation's
"no vision" scope limit so the specs match the code.

## What Changes

- Extend the AI provider layer with **vision report generation**
  (`generate_vision_health_report`) for Gemini, OpenAI, and Ollama, sending a
  prompt plus a base64 image and returning the model's text.
- Add a **scheduled, camera-based health check** per grow space that captures a
  camera snapshot, gathers mapped metric states and operator cultivation context,
  builds a quality-first agronomy prompt, calls the provider, and parses strict
  JSON into a structured result (score, confidence, severity, summary,
  observations, issues, recommended actions, feeding schedule).
- Add **result persistence and retention**: store health results in HA storage,
  keep a rolling history bounded by a configurable retention window, and expose
  the latest result and history count.
- Add **health entities** per grow space: an AI health **score** sensor, a
  **summary** sensor, a **feeding schedule** sensor, a **last-check** timestamp
  sensor, a **critical alert** binary sensor, and a **Run AI Health Check** button.
- Add **notifications** when the score is at or below a configurable severe
  threshold: always a persistent notification, plus an optional user notify
  service.
- Add a **`run_ai_health_check` service** to run a check on demand for one or all
  loaded grow spaces, and schedule periodic checks plus a delayed startup check.
- **BREAKING (spec-level only):** remove the foundation requirement that forbade
  vision/advice provider calls.

## Capabilities

### New Capabilities
- `ai-health-monitoring`: Scheduled and on-demand camera-based AI grow-health
  checks — snapshot capture, prompt construction, JSON parsing, scoring, feeding
  schedule, persistence/retention, health entities, notifications, and the
  `run_ai_health_check` service.

### Modified Capabilities
- `ai-provider-abstraction`: Add a vision report-generation requirement for the
  registered providers and **remove** the "Foundation scope limit" requirement
  that prohibited vision/advice calls.

## Impact

- **New code**: `ai/health_checks.py` (runtime, prompt, parsing, persistence,
  notifications), `generate_vision_health_report` in `ai/providers.py`, AI health
  entities across `sensor.py`, `binary_sensor.py`, `button.py`, scheduling and the
  `run_ai_health_check` service in `__init__.py`, and `services.yaml`.
- **Constants**: `CONF_AI_HEALTH_INTERVAL_HOURS`, `CONF_AI_SEVERE_THRESHOLD`,
  `CONF_AI_NOTIFY_SERVICE`, `CONF_AI_RESULT_RETENTION_DAYS`, and `STAGE_TARGETS`.
- **Config/UX**: AI-health settings added to config and options flows; requires a
  configured provider/model and a mapped camera role to run.
- **External calls**: One provider vision request per check (plus camera snapshot);
  no calls when no provider/model or camera is configured.
- **Secrets**: Provider API keys remain redacted in logs and diagnostics; health
  history stored per entry contains no secrets.
