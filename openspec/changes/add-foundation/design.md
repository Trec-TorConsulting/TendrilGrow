# Design: add-foundation

## Context

TendrilGrow is a new, single-package Home Assistant offering (integration +
dashboards + AI advisor + automations) distributed through HACS for indoor
cultivation. This change establishes the foundation only: a HACS-compliant custom
integration, a flexible grow-space data model, user-driven configuration, and a
pluggable AI provider abstraction (no live AI calls yet).

Current state: empty repository with OpenSpec initialized. The maintainer runs a
live Home Assistant with two RDWC Vivosun tents (3x3 mothers with 200W LED +
Reolink camera; 4x4 with 400W LED + Reolink 4K camera), Vivosun E42a+ controllers,
and sensors for temp/humidity (VPD), PPFD/lux, and pH/EC/TDS. This live setup is
the primary validation source, but the design must generalize to any user.

Constraints:
- Must pass `hassfest` and HACS validation.
- Target the latest Home Assistant release and the latest Python it supports.
- Async-only, config-flow based (no YAML config), following HA quality-scale.
- No hardcoded entity ids; users map their own entities.
- Secrets (AI keys) must never be logged or exposed in diagnostics.

Companion integrations in the maintainer's live setup (entities are user-provided):
Vivosun HACS integration exposes the E42a+ controllers (lights/fans/inline fans),
and the Tuya HACS integration exposes the RDWC header-bucket water monitors.

## Goals / Non-Goals

**Goals:**
- A validated `custom_components/tendrilgrow/` skeleton installable via HACS.
- Config flow + options flow to create/edit grow spaces and map entities.
- A flexible domain model (spaces → sites, sensor/control roles, derived metrics,
  targets/schedules) that fits RDWC and other grow types.
- An AI provider interface with user selection and per-provider credential config.
- Dynamic discovery of a provider's available models after credentials are entered.
- CI: hassfest, HACS validation, and lint.

**Non-Goals:**
- Lovelace dashboard cards (later change).
- Live AI advice or camera/vision reviews (later change).
- Automations engine (later change).
- A dedicated Vivosun/Tuya device integration — foundation maps existing HA entities only.

## Decisions

### Distribution: HACS custom integration (not a Supervisor Add-on)
Chosen because the product is primarily an integration plus frontend cards, which
HACS distributes natively; a Supervisor Add-on would exclude Home Assistant
Container/Core users and add Docker packaging overhead. Cards ship later via HACS
frontend. Alternative (Add-on) rejected for reach and complexity.

### One config entry per grow space
Each grow space is its own config entry, so it owns its equipment mappings, grow
type, targets/schedules, and settings independently. Rationale: the maintainer's
spaces have distinct equipment and requirements, and one-entry-per-space maps
cleanly to an HA device/service per grow, gives per-space reload/enable/disable,
and keeps grows isolated. Global settings (e.g., a default AI provider) can be
shared via a lightweight default or repeated per entry. Alternative (single entry
with spaces in options) was rejected because it couples unrelated grows and
complicates per-space lifecycle.

### Entity mapping over auto-discovery
Users explicitly map entities to roles via selectors. Rationale: grow hardware is
heterogeneous and device_class/area heuristics are unreliable across setups.
Auto-discovery may be offered later as a convenience that pre-fills mappings.

### Extensible role-based model
Sensors and controls are modeled as named roles bound to entity ids, with an
extensible role registry rather than fixed fields. Rationale: supports varied
sensors, grow types, and future roles without schema churn. Derived metrics (e.g.,
VPD) are computed from roles when inputs exist and report unavailable otherwise.

### AI provider abstraction (strategy pattern)
A `AIProvider` interface with concrete implementations (Gemini, Ollama, OpenAI)
selected at runtime from stored config. Foundation ships the interface, selection,
credential capture/validation, and model discovery. After the user enters
credentials/endpoint, the flow calls the provider's list-models endpoint and
presents the available models to choose from. Rationale: lets users pick their
model and keeps consumers decoupled. Grow advice and vision calls remain out of
scope. No third-party AI SDKs are pinned in the manifest to keep the install light
— model discovery uses generic HTTP where possible; provider SDKs are added per
provider in a later change.

### Secrets handling
Provider credentials are stored in the config entry data and redacted from logs and
diagnostics. Rationale: HA config-entry storage is the standard mechanism; explicit
redaction prevents accidental leakage.

## Risks / Trade-offs

- **Per-space entries add setup steps for multi-grow users** → Keep the flow short
  with sensible defaults and allow copying settings from an existing space later.
- **No pinned AI SDKs in foundation** → Model discovery relies on provider REST
  endpoints; handle providers whose listing needs an SDK by deferring those to the
  later change. AI advice/vision stay disabled until wired.
- **Model discovery makes a live call during config** → Treat it as connectivity
  validation; on failure, surface a clear error and let the user retry or enter a
  model manually.
- **Entity mapping burden on users** → Mitigate with clear selectors, optional
  roles, and later optional auto-discovery pre-fill.
- **Vivosun/Tuya/Reolink depend on external integrations** → Foundation only
  references user-provided entities; document required companion integrations
  (Vivosun HACS, Tuya HACS, camera) in README.
- **Model generalization vs. maintainer's specifics** → Validate against live data
  but keep the role registry generic; avoid RDWC-only assumptions.

## Migration Plan

Greenfield — no existing installs. Rollout: publish repo, add HACS custom
repository, install, then add one config entry per grow space via the config flow.
Rollback: remove each grow-space config entry and the integration (no external
state). Keep grow-space ids stable to ease future dashboard/automation linkage.

## Resolved Decisions

- Target the latest Home Assistant release and the latest Python it supports.
- One config entry per grow space.
- Vivosun controls via the Vivosun HACS integration; RDWC water monitors via the
  Tuya HACS integration — foundation maps these entities only.
- Integration `domain` slug: `tendrilgrow`.
- Initial providers: Gemini, Ollama, OpenAI, each with dynamic model listing after
  credentials are entered.
