# Proposal: add-ai-provider-expansion

## Why

TendrilGrow supports Gemini, OpenAI, and Ollama. Growers increasingly want
Anthropic Claude (strong vision), Azure OpenAI (enterprise/private), and any
OpenAI-compatible endpoint (OpenRouter, LM Studio, vLLM, LiteLLM). Adding them
widens choice for both model discovery and the camera-vision health reports. This
is a **new, not-yet-built** change that extends the existing provider layer.

## What Changes

- Add three providers to the provider registry, each implementing the existing
  interface (selection, credential/endpoint config, model discovery, and vision
  report generation):
  - **Anthropic Claude** — API key; discovery via the models endpoint; vision via
    the messages API with base64 image blocks.
  - **Azure OpenAI** — resource endpoint, API key, API version, and deployment
    name (used as the model); discovery lists deployments or falls back to manual
    deployment entry; vision via the deployment's chat-completions endpoint.
  - **OpenAI-compatible (custom endpoint)** — base URL and optional API key;
    discovery and vision via the OpenAI-compatible `/v1/models` and
    `/v1/chat/completions` routes.
- Add a **vision-capability declaration** per provider so AI health checks can
  detect and clearly report when a selected provider/model cannot do vision,
  instead of failing opaquely.
- Extend **provider validation** and the **credentials step** in the config flow to
  collect the new per-provider fields with actionable errors.

## Capabilities

### New Capabilities
<!-- None — this extends the existing provider layer. -->

### Modified Capabilities
- `ai-provider-abstraction`: Add Anthropic, Azure OpenAI, and OpenAI-compatible
  providers (config, discovery, vision) and a per-provider vision-capability
  declaration surfaced to AI health checks.

## Impact

- **Code**: new `ProviderDefinition` entries and per-provider discovery/vision
  branches in `ai/providers.py`; new credential fields and validation in
  `config_flow.py`; new constants (`PROVIDER_ANTHROPIC`, `PROVIDER_AZURE_OPENAI`,
  `PROVIDER_OPENAI_COMPAT`, and their config keys) in `const.py`.
- **Config/UX**: provider dropdown gains three options; the credentials step shows
  the right fields per provider (Azure needs endpoint + api version + deployment).
- **Secrets**: new API keys added to `SENSITIVE_KEYS`; redacted in logs/diagnostics.
- **Tests**: discovery, validation, vision-capability gating, and error handling for
  each new provider (mocked HTTP).
- **No breaking changes**: existing Gemini/OpenAI/Ollama behavior is unchanged;
  additions are backward compatible.
