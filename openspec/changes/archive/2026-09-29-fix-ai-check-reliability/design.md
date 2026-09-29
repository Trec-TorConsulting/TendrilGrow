## Context

`generate_vision_health_report` uses the shared aiohttp session with no timeout. Gemini puts the API key in the query string for both model list and `generateContent`. `run_ai_health_check` sets `state.running` and never checks it. Setup always schedules a check 120 seconds later, and the interval scheduler always fires; both raise `ai_provider_not_configured` when AI is off. `_coerce_result` iterates `issues` and the other list fields with `for item in value`, so a string becomes characters. Options cannot change provider, model, or API key after create.

This change does not add providers and does not touch Tuya or LocalTuya credentials.

## Goals / Non-Goals

**Goals:**

- Provider calls fail fast on a timeout.
- One check per space at a time.
- No scheduled or startup call when provider or model is missing.
- Gemini key stays out of URLs, logs, and diagnostics.
- List fields stay lists. Fenced JSON still parses.
- Options can rotate provider, model, key, and base URL without wiping a blank key.

**Non-Goals:**

- Anthropic, Azure OpenAI, or generic OpenAI-compatible endpoints.
- Changing agronomy prompt content.
- Image retention or sending snapshots anywhere except the configured provider.

## Decisions

### Timeout on the client call

Pass `timeout=aiohttp.ClientTimeout(total=60)` on provider GET and POST. On timeout, raise `ProviderExecutionError` with a short message that does not include the URL (the URL may contain a key during the transition). 60 seconds covers a vision response without wedging the scheduler.

### Single-flight per entry

If `state.running` is already true, return the latest result (or raise a dedicated "already running" error for the service) and do not start another snapshot or HTTP call. Clear `running` in `finally`.

### Schedule only when configured

Create the interval timer and the 120-second startup callback only when provider is not `none` and model is non-empty. Options reload already reloads the entry, so changing credentials rebuilds the schedule.

### Gemini key as header

Use `x-goog-api-key` (or the current header Google documents for the Generative Language API) and remove `?key=` from both the models URL and `generateContent`. Do not log the request URL at info level.

### Coerce lists, then parse fences

If a field is a string, wrap it as one item. If it is not a list or string, use an empty list. Strip a leading ``` fence line and a trailing fence line as whole lines; do not `str.strip` backticks from the body.

### Diagnostics

Omit `raw_response` from the diagnostics payload. Keep API keys in `SENSITIVE_KEYS`.

### Options credentials

Add provider, model, API key, and base URL to the options flow. Blank API key keeps the stored key, matching the Tuya secret field. Do not show or write Tuya fields differently in this change.

## Risks / Trade-offs

- [60s timeout cuts off a slow local model] → Ollama on a small machine may need longer. Use 120s for Ollama and 60s for cloud providers.
- [Header name drifts] → Pin the header in one helper and test that the request URL has no `key=` query.
- [Overlapping button click looks like a failure] → Service response says a check is already running, and the UI keeps the previous result.

## Migration Plan

No stored history migration. Existing API keys remain in `entry.data` until an options save copies updates into options; merged config already prefers options. A blank options key must not overwrite data.

## Open Questions

None.
