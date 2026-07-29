# Tasks: add-ai-provider-expansion

> Forward-looking change — **not yet implemented**. Work top to bottom; each task
> is independently verifiable. Mirror the existing Gemini/OpenAI/Ollama branches in
> `ai/providers.py`. Do not check a box until its verification passes.

## 1. Constants and registry

- [ ] 1.1 Add `PROVIDER_ANTHROPIC`, `PROVIDER_AZURE_OPENAI`, `PROVIDER_OPENAI_COMPAT` and Azure keys (`CONF_AZURE_ENDPOINT`, `CONF_AZURE_API_VERSION`, `CONF_AZURE_DEPLOYMENT`) (`const.py`)
- [ ] 1.2 Add each new provider's secret key(s) to `SENSITIVE_KEYS`
- [ ] 1.3 Add `supports_vision: bool` to `ProviderDefinition` (default True) and register the three providers in `PROVIDERS` (`ai/providers.py`)

## 2. Model discovery

- [ ] 2.1 Anthropic: `GET /v1/models` with `x-api-key` + `anthropic-version`; map ids
- [ ] 2.2 Azure OpenAI: list deployments with `api-key`; fall back to the entered deployment name when not permitted
- [ ] 2.3 OpenAI-compatible: `GET {base_url}/v1/models` (Bearer if key present); map `data[].id`
- [ ] 2.4 Unit-test discovery success and failure for each provider (mocked HTTP)

## 3. Vision generation

- [ ] 3.1 Anthropic: `POST /v1/messages` with base64 image block; extract text from `content[]`
- [ ] 3.2 Azure OpenAI: `POST {endpoint}/openai/deployments/{deployment}/chat/completions?api-version=<v>` with `api-key`, OpenAI-format `image_url`
- [ ] 3.3 OpenAI-compatible: `POST {base_url}/v1/chat/completions` (reuse OpenAI extractor)
- [ ] 3.4 Add `provider_supports_vision(provider)` and gate AI health checks; raise `ProviderExecutionError("provider_no_vision")` when unsupported
- [ ] 3.5 Unit-test vision success and HTTP-error paths for each provider (mocked)

## 4. Validation

- [ ] 4.1 Extend `validate_provider_config`: Anthropic (api_key); Azure (endpoint http/https, api_key, api_version, deployment); compat (base_url http/https, api_key optional)
- [ ] 4.2 Unit-test each provider's missing-field errors

## 5. Config flow

- [ ] 5.1 Add the three providers to the provider dropdown (`async_step_ai_provider`)
- [ ] 5.2 Render provider-specific credential fields in `async_step_ai_credentials` (Azure shows endpoint/api_version/deployment; compat shows base_url + optional key)
- [ ] 5.3 Reuse the existing discover-then-select flow and the manual-model fallback
- [ ] 5.4 Add `strings.json`/`translations/en.json` labels for the new fields
- [ ] 5.5 Config-flow tests: select each provider, discover, and finish an entry (mocked)

## 6. Validation and docs

- [ ] 6.1 Full test pass; `hassfest`/HACS/lint pass
- [ ] 6.2 Update README AI-provider list and note vision-capable model requirement
- [ ] 6.3 Confirm diagnostics redact all new API keys
