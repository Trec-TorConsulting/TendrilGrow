# Design: add-ai-provider-expansion

## Context

The provider layer (`ai/providers.py`) already defines a `ProviderDefinition` with
`list_models` and a `generate_vision_health_report` dispatcher branching per
provider key. This change adds three providers by extending both, plus a small
capability flag so vision-only features can gate on provider support. A cheaper
implementation model should mirror the existing Gemini/OpenAI/Ollama branches.

Constraints:
- Async-only; use Home Assistant's shared aiohttp session.
- No third-party SDKs — call REST endpoints directly.
- Keep the existing interface; add providers without changing consumers.

## New providers

Constants (`const.py`):
```python
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_AZURE_OPENAI = "azure_openai"
PROVIDER_OPENAI_COMPAT = "openai_compat"
CONF_AZURE_ENDPOINT = "azure_endpoint"
CONF_AZURE_API_VERSION = "azure_api_version"
CONF_AZURE_DEPLOYMENT = "azure_deployment"
# reuse CONF_API_KEY and CONF_BASE_URL where possible
```

### Anthropic Claude
- Fields: `CONF_API_KEY`.
- Discovery: `GET https://api.anthropic.com/v1/models` with headers
  `x-api-key: <key>`, `anthropic-version: 2023-06-01`; map `data[].id`.
- Vision: `POST https://api.anthropic.com/v1/messages` with body
  `{ model, max_tokens, messages: [{ role: "user", content: [ {type:"text",text:prompt},
  {type:"image", source:{type:"base64", media_type:mime, data:encoded}} ] }] }`;
  extract text from `content[].text`.
- `supports_vision = True`.

### Azure OpenAI
- Fields: `CONF_AZURE_ENDPOINT` (e.g. `https://<res>.openai.azure.com`),
  `CONF_API_KEY`, `CONF_AZURE_API_VERSION` (e.g. `2024-06-01`),
  `CONF_AZURE_DEPLOYMENT` (deployment name = model).
- Discovery: attempt `GET {endpoint}/openai/deployments?api-version=<v>` with header
  `api-key`; if unavailable/forbidden, fall back to using the entered deployment
  name as the single model (manual entry), consistent with the existing
  discovery-failure fallback.
- Vision: `POST {endpoint}/openai/deployments/{deployment}/chat/completions?api-version=<v>`
  with header `api-key`, OpenAI-format messages incl. `image_url` data URI.
- `supports_vision = True`.

### OpenAI-compatible (custom endpoint)
- Fields: `CONF_BASE_URL`, optional `CONF_API_KEY`.
- Discovery: `GET {base_url}/v1/models` (Bearer if key present); map `data[].id`.
- Vision: `POST {base_url}/v1/chat/completions` (OpenAI format).
- `supports_vision = True` (the user selects a vision-capable model).

## Vision-capability declaration

Add `supports_vision: bool` to `ProviderDefinition` (default True for these). AI
health checks call a helper `provider_supports_vision(provider)`; when false (future
non-vision providers), the check raises a clear `ProviderExecutionError`
("provider_no_vision") instead of a malformed request. Existing providers keep
`supports_vision = True`.

## Config-flow changes

Extend `async_step_ai_provider` options with the three new keys, and
`async_step_ai_credentials` to render provider-specific fields:
- Anthropic: `api_key` (password).
- Azure OpenAI: `azure_endpoint`, `api_key` (password), `azure_api_version`,
  `azure_deployment`.
- OpenAI-compatible: `base_url`, optional `api_key` (password).
Then run existing `validate_provider_config` + `discover_models`, reusing the
manual-model fallback path on discovery failure.

## Validation

Extend `validate_provider_config`:
- Anthropic: require `api_key`.
- Azure: require `azure_endpoint` (http/https), `api_key`, `azure_api_version`,
  `azure_deployment`.
- OpenAI-compatible: require `base_url` (http/https); `api_key` optional.

## Secrets

Add the new API keys to `SENSITIVE_KEYS`. Azure/compat endpoints are not secret but
avoid logging full URLs with embedded tokens. Diagnostics already redact
`SENSITIVE_KEYS`.

## Goals / Non-Goals

**Goals:** three widely-requested providers with discovery + vision; clear vision
capability gating; backward compatibility.

**Non-Goals:** streaming responses, function/tool calling, per-provider advanced
params beyond what health checks need.

## Risks / Trade-offs

- **Azure deployment vs. model semantics** → treat deployment as model; discovery
  falls back to manual entry when the deployments list is not permitted.
- **Compat endpoints vary** → rely on the OpenAI-compatible contract; surface the
  raw HTTP error body (already done by `_read_json_or_raise`).
- **Wrong model for vision** → capability flag + actionable error; document that the
  user must pick a vision-capable model.

## Acceptance criteria

- Each new provider appears in the provider dropdown and shows correct credential
  fields.
- Valid credentials discover models (or fall back to manual) and a vision health
  check returns a parsed result.
- Missing required fields produce actionable validation errors.
- New API keys are redacted in diagnostics.
- Mocked-HTTP unit tests cover discovery, validation, vision success, and error
  paths for all three providers.

## Migration Plan

Additive and backward compatible. Existing entries keep their provider. No data
migration. Rollback: remove the new registry entries and config fields.
