# Design: add-ai-vision-health

## Context

The foundation shipped provider selection and model discovery but explicitly
forbade live advice/vision calls. The maintainer's grows have cameras
(Reolink) and reservoir/environment telemetry, enabling a multimodal health
review. This change (already implemented) adds that review as a scheduled and
on-demand capability. It is documented here so `openspec/specs/` matches shipped
behavior.

Constraints:
- Async-only; use Home Assistant's shared aiohttp session and camera helpers.
- A check requires a configured provider + model and a mapped `camera` role.
- Provider API keys must never be logged or exposed in diagnostics.
- Results persist across restarts and are bounded by a retention window.

## Goals / Non-Goals

**Goals:**
- Produce a structured, quality-first health result from image + telemetry +
  cultivation context.
- Surface the result through HA entities and notify on critical scores.
- Persist a bounded history; support scheduled and manual runs.

**Non-Goals:**
- Automated control actions in response to results (future automations change).
- Multi-camera fusion or video analysis (single snapshot per check).
- Provider fine-tuning or long-term analytics/graphs (dashboards change).

## Decisions

### Vision execution in the provider layer
`generate_vision_health_report(provider, model, config, prompt, image_bytes,
mime_type)` encodes the image as base64 and posts to each provider's multimodal
endpoint (Gemini `:generateContent`, OpenAI `chat/completions` with `image_url`,
Ollama `/api/chat` with `images`), returning extracted text. Rationale: keeps
provider-specific wire formats behind one interface so the health runtime is
provider-agnostic.

### Strict-JSON contract with tolerant parsing
The prompt demands strict JSON with a fixed key set; `_coerce_result` extracts the
JSON object (tolerating code fences/prose), clamps `score`/`confidence` to 0–100,
and falls back to an "unknown" result carrying the raw text when parsing fails.
Rationale: models occasionally wrap JSON; the runtime must never crash on output.

### Quality-first agronomy prompt with stage calibration
`_build_prompt` injects per-stage target ranges (`STAGE_TARGETS`), a nutrient
mobility rubric, and total-reservoir dosing rules, and includes operator context
(strain, week, reservoir volume, nutrients) read from grow-context helper
entities. Rationale: grounds the model in the user's setup and calibrates scoring.

### Snapshot capture with proxy fallback
`_async_get_camera_snapshot` uses `camera.async_get_image`, falling back to the
authenticated camera proxy URL if the entity lookup races at startup. Rationale:
robustness during HA startup ordering.

### Persistence, retention, and dispatch
Results are stored via HA `Store` per entry; history is trimmed to the retention
window on each run. A dispatcher signal notifies entities to refresh. An ephemeral
in-memory store is used when the storage backend is unavailable (tests).

### Notifications on critical score
When `score <= severe_threshold`, always create a persistent notification and,
when configured, call the user's `notify` service. Rationale: guarantee a visible
alert while allowing richer routing.

### Scheduling
`async_track_time_interval` drives periodic checks (interval hours, min 1) and
`async_call_later` runs one delayed startup check (~120s) so cameras/telemetry are
ready. The `run_ai_health_check` service triggers on-demand runs for one or all
entries.

## Risks / Trade-offs

- **Model/output variability** → strict-JSON prompt + tolerant parser + confidence
  field; unknown results are surfaced rather than dropped.
- **Provider cost/rate** → interval configurable in hours; manual runs are
  explicit; checks are skipped without provider/model/camera.
- **Startup races** → delayed startup check and camera proxy fallback.
- **Secret exposure** → keys passed only to provider calls, redacted everywhere
  else; stored history contains no credentials.

## Migration Plan

Additive — checks only run when a provider, model, and camera are configured.
Existing entries without AI configured are unaffected. Removing the foundation's
"no vision" scope limit is a spec-level change only; no data migration needed.
