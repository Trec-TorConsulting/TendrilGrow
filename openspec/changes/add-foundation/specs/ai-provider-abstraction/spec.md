## ADDED Requirements

### Requirement: Pluggable AI provider interface
The system SHALL define a common AI provider interface so that concrete providers
(for example Google Gemini, Ollama, OpenAI/ChatGPT) can be added without changing
consumer code.

#### Scenario: Add a provider without consumer changes
- **WHEN** a new provider implementing the interface is registered
- **THEN** it becomes selectable by users without modifying features that consume
  the interface

### Requirement: User-selectable provider
The integration SHALL let the user choose which AI provider to use from the
available providers via the configuration UI.

#### Scenario: Select a provider
- **WHEN** the user selects Gemini as the AI provider
- **THEN** the selection is stored and used as the active provider

#### Scenario: No provider selected
- **WHEN** no AI provider is configured
- **THEN** the integration operates normally and AI-dependent features are disabled

### Requirement: Per-provider credentials and endpoints
The integration SHALL collect and store the configuration each provider needs,
such as an API key for Gemini/OpenAI or a base URL and model name for Ollama, and
MUST treat these values as secrets.

#### Scenario: Configure Gemini API key
- **WHEN** the user selects Gemini and enters an API key
- **THEN** the key is stored securely and is not exposed in logs or diagnostics

#### Scenario: Configure a local Ollama endpoint
- **WHEN** the user selects Ollama and provides a base URL and model name
- **THEN** those values are stored and associated with the Ollama provider

### Requirement: Provider validation
The configuration flow SHALL validate provider settings (for example presence of a
required API key or a reachable endpoint) before saving, and report actionable
errors when validation fails.

#### Scenario: Reject incomplete provider config
- **WHEN** the user selects a provider but omits a required credential
- **THEN** the flow reports the missing field and does not save the configuration

### Requirement: Dynamic model discovery
The integration SHALL query the selected provider for its available models after
the user provides valid credentials/endpoint, and present them for the user to
choose from. On discovery failure it MUST report an actionable error and allow the
user to retry or enter a model identifier manually.

#### Scenario: List models after credentials
- **WHEN** the user enters a valid Gemini API key
- **THEN** the flow fetches Gemini's available models and lets the user select one

#### Scenario: List local Ollama models
- **WHEN** the user provides a reachable Ollama base URL
- **THEN** the flow lists the models available on that Ollama server for selection

#### Scenario: Discovery failure fallback
- **WHEN** model discovery fails (unreachable endpoint or invalid credentials)
- **THEN** the flow reports the error and lets the user retry or enter a model manually

### Requirement: Foundation scope limit
The foundation SHALL ship only the provider interface, selection, credential
configuration, and model discovery. Grow advice and vision reviews are out of scope
for this change; the only live provider call permitted is model discovery.

#### Scenario: No advice or vision in foundation
- **WHEN** the foundation is installed and a provider and model are configured
- **THEN** no grow-advice or vision requests are sent until a later change adds them
