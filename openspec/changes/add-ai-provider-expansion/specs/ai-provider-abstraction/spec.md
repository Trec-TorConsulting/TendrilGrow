## ADDED Requirements

### Requirement: Extended provider set
The provider layer SHALL additionally offer Anthropic Claude, Azure OpenAI, and an
OpenAI-compatible custom-endpoint provider, each implementing the common interface:
user selection, per-provider credential/endpoint configuration, model discovery,
and vision report generation. Existing providers MUST remain unchanged.

#### Scenario: Select Anthropic
- **WHEN** the user selects Anthropic and enters a valid API key
- **THEN** the flow discovers Anthropic models and stores the selection

#### Scenario: Select an OpenAI-compatible endpoint
- **WHEN** the user selects the OpenAI-compatible provider and enters a base URL
- **THEN** the flow lists models from that endpoint's OpenAI-compatible API

#### Scenario: Existing providers unaffected
- **WHEN** a grow space already uses Gemini, OpenAI, or Ollama
- **THEN** its behavior is unchanged after the new providers are added

### Requirement: Azure OpenAI configuration
The Azure OpenAI provider SHALL collect a resource endpoint, API key, API version,
and deployment name (used as the model), and SHALL discover deployments where
permitted, falling back to using the entered deployment name when discovery is not
available.

#### Scenario: Configure Azure OpenAI
- **WHEN** the user provides endpoint, API key, API version, and deployment
- **THEN** the provider stores them and uses the deployment as the model

#### Scenario: Deployment discovery fallback
- **WHEN** listing deployments is not permitted for the credentials
- **THEN** the flow uses the entered deployment name as the model without error

### Requirement: Vision capability declaration
Each provider SHALL declare whether it supports vision, and AI health checks MUST
report an actionable error when the selected provider does not support vision rather
than sending a malformed request.

#### Scenario: Non-vision provider rejected for health checks
- **WHEN** an AI health check runs against a provider that does not support vision
- **THEN** the check fails with a clear "provider does not support vision" error

#### Scenario: Vision-capable provider proceeds
- **WHEN** an AI health check runs against a vision-capable provider and model
- **THEN** the check sends the image request and returns a parsed result

### Requirement: Extended provider validation and secrets
Provider validation SHALL enforce each new provider's required fields with
actionable errors, and each new API key MUST be treated as a secret and redacted
from logs and diagnostics.

#### Scenario: Missing Azure field
- **WHEN** the user selects Azure OpenAI but omits the API version or deployment
- **THEN** the flow reports the missing field and does not save the configuration

#### Scenario: New keys redacted
- **WHEN** diagnostics are generated for a space using a new provider
- **THEN** that provider's API key is redacted from the output
