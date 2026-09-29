## MODIFIED Requirements

### Requirement: Per-provider credentials and endpoints
The integration SHALL collect and store the configuration each provider needs,
such as an API key for Gemini/OpenAI or a base URL and model name for Ollama, and
MUST treat these values as secrets. The options flow MUST allow updating the
provider, model, API key, and base URL after the config entry exists. A blank API
key on that form MUST keep the stored key. Provider HTTP calls MUST include a
timeout. The Gemini API key MUST be sent in a request header and MUST NOT appear
in the request URL.

#### Scenario: Configure Gemini API key
- **WHEN** the user selects Gemini and enters an API key
- **THEN** the key is stored securely and is not exposed in logs or diagnostics

#### Scenario: Configure a local Ollama endpoint
- **WHEN** the user selects Ollama and provides a base URL and model name
- **THEN** those values are stored and associated with the Ollama provider

#### Scenario: Blank options key keeps the stored key
- **WHEN** the operator saves options and leaves the API key blank
- **THEN** the previously stored API key is unchanged

#### Scenario: Gemini request URL has no key
- **WHEN** the integration calls Gemini for model discovery or a vision report
- **THEN** the request URL does not contain the API key

### Requirement: Vision report generation
Each registered provider (Gemini, OpenAI, Ollama) SHALL support generating a text
report from a text prompt plus a single image, encoding the image for the
provider's multimodal endpoint and returning the extracted text. On transport or
HTTP error it MUST raise an actionable execution error, and it MUST reject an
unsupported provider. Each provider HTTP call MUST fail with an execution error
if it exceeds its timeout, and that error MUST NOT include the API key.

#### Scenario: Generate a report from image and prompt
- **WHEN** a configured provider and model receive a prompt and a snapshot image
- **THEN** the provider returns the model's text response

#### Scenario: Provider error is surfaced
- **WHEN** the provider endpoint returns an error status
- **THEN** an execution error is raised with the provider and status detail

#### Scenario: Provider call times out
- **WHEN** the provider does not respond within the timeout
- **THEN** the integration raises an execution error and does not leave the check running

## ADDED Requirements

### Requirement: Diagnostics omit raw model output
Diagnostics for a grow space MUST NOT include the AI check `raw_response` body.

#### Scenario: Diagnostics download
- **WHEN** the operator downloads diagnostics after a health check
- **THEN** the payload does not contain `raw_response`
