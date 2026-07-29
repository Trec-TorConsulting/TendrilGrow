## ADDED Requirements

### Requirement: Vision report generation
Each registered provider (Gemini, OpenAI, Ollama) SHALL support generating a text
report from a text prompt plus a single image, encoding the image for the
provider's multimodal endpoint and returning the extracted text. On transport or
HTTP error it MUST raise an actionable execution error, and it MUST reject an
unsupported provider.

#### Scenario: Generate a report from image and prompt
- **WHEN** a configured provider and model receive a prompt and a snapshot image
- **THEN** the provider returns the model's text response

#### Scenario: Provider error is surfaced
- **WHEN** the provider endpoint returns an error status
- **THEN** an execution error is raised with the provider and status detail

## REMOVED Requirements

### Requirement: Foundation scope limit
**Reason**: The foundation's prohibition on vision/advice calls is superseded by
the shipped camera-based AI health monitoring capability.
**Migration**: No action required. Vision calls run only when a provider, model,
and camera role are configured; otherwise no AI calls are made.
