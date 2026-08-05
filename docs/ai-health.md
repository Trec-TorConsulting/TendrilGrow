# AI health checks

TendrilGrow can analyze a camera snapshot of your plants with a vision-capable
AI model and return an agronomy-style report.

## What a check produces

Each check returns:

- A **health score** from 0–100 (quality-first agronomy scoring).
- **Observations** about the plants and canopy.
- **Issues** the model believes it sees.
- **Recommended actions**.
- A **dynamic feeding schedule** suggestion.

Results populate the AI health entities (score, summary, feeding schedule, last
check, and a critical alert) and are stored with a retention window.

## Providers

Select a provider per grow space:

| Provider | Notes |
| --- | --- |
| `None` | AI disabled for this grow space. |
| `Gemini` | Google Gemini. |
| `OpenAI` | OpenAI. |
| `Ollama` | Self-hosted/local models via an Ollama endpoint. |

After you enter credentials (API key or endpoint), TendrilGrow discovers the
available models so you can pick one. If discovery fails, you can enter a model
name manually.

!!! info "Requirements for vision checks"
    You must map a `camera` entity and choose a **vision-capable** model. Without
    a camera and a vision model, AI health entities are not created.

## Scheduling and on-demand runs

- **Scheduled:** checks run on the configured interval (default **12 hours**).
- **On demand:** press the **Run AI Health Check** button, or call
  [`tendrilgrow.run_ai_health_check`](services.md#tendrilgrowrun_ai_health_check).

## Critical alerts

If a score is at or below the **critical threshold** (default **20**),
TendrilGrow raises a persistent notification and, if configured, calls your
`notify.*` service. Alerts are de-duplicated so you are not spammed.

## Stage-aware objectives

Scoring adapts to the grow stage set on the **Growth Stage** helper:

- **Mothers** are judged on health and structure (never flowered).
- **Clones** are judged on rooting.
- **Flowering** stages are judged on quality.
- **Dry/cure** stages are judged on drying/curing rather than reservoir
  chemistry.

Per-stage reservoir targets (pH, EC, VPD) calibrate the prompt; post-harvest
stages fall back to best-practice guidance.

## Grounding with cultivation context

The advisor is grounded by the editable cultivation-context helpers (strain,
week in stage, targets, reservoir volume, makeup water type, nutrients, flush
status, and more). Keeping these accurate improves the quality of the advice.
See [Entities](entities.md).

## History and retention

Each result is persisted with its timestamp and kept for the configured
retention period (default **30 days**).

## Secrets safety

API keys are treated as sensitive: they are redacted in diagnostics and logs.
Never paste real keys into issues or discussions.
