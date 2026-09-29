## Why

AI health checks can hang (no HTTP timeout), overlap (startup, schedule, and the button ignore `running`), and run when no provider is configured. The Gemini API key is sent in the query string. A model that returns `issues` as a string is stored as one character per issue. Operators cannot rotate the AI key or model after the config entry is created.

## What Changes

- Bound every provider HTTP call with a timeout.
- Run at most one health check per grow space at a time. Skip the startup and interval schedulers when provider or model is unset.
- Send the Gemini API key in a header, not the URL.
- Accept list fields only when the model returned a list. Parse fenced JSON without stripping backticks out of the payload.
- Keep `raw_response` out of diagnostics, or redact it.
- Let the options flow change AI provider, model, API key, and base URL. A blank key keeps the stored key.

## Capabilities

### New Capabilities

### Modified Capabilities

- `ai-health-monitoring`: Checks time out, do not overlap, do not start when unconfigured, and coerce structured fields safely.
- `ai-provider-abstraction`: Gemini authentication is not placed in the request URL, and provider credentials can be updated from the options flow.

## Impact

- `ai/providers.py`, `ai/health_checks.py`, `__init__.py` schedulers, `config_flow.py` options, `diagnostics.py`.
- Tests for overlap, unconfigured startup, string-typed `issues`, fenced JSON, and a blank options key that preserves the existing key.
- Does not add Anthropic, Azure, or a generic OpenAI-compatible provider (that remains `add-ai-provider-expansion`).
- Does not touch Tuya or LocalTuya credentials.
