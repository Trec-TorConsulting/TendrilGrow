# Installation

TendrilGrow is distributed as a HACS custom integration.

## Prerequisites

- Home Assistant **2026.2.0** or newer.
- [HACS](https://hacs.xyz/) installed and configured.
- Any companion integrations that expose the entities you want to map, for
  example:
    - A controller integration for lights/fans (the maintainer uses the Vivosun
      HACS integration).
    - The Tuya HACS integration for reservoir water monitors (optional).
    - A camera integration (required for AI vision health checks).

!!! info "No hardcoded entities"
    TendrilGrow never assumes specific entity IDs. You map your own entities
    during setup, so any brand of sensor, controller, or camera works.

## Install via HACS

1. Open **HACS** in Home Assistant.
2. Open the menu (top-right) and choose **Custom repositories**.
3. Add the repository URL
   `https://github.com/Trec-TorConsulting/TendrilGrow`.
4. Select category **Integration**.
5. Install **TendrilGrow** from HACS.
6. **Restart Home Assistant.** Custom integrations are not loaded until a
   restart.
7. Go to **Settings → Devices & Services → Add Integration** and add
   **TendrilGrow**.

## Manual installation

If you prefer not to use HACS, copy the integration folder into your Home
Assistant configuration:

```text
/config/custom_components/tendrilgrow
```

Then restart Home Assistant and add the integration from **Settings → Devices &
Services**. A packaged `tendrilgrow.zip` is attached to each
[GitHub release](https://github.com/Trec-TorConsulting/TendrilGrow/releases).

## First-time setup

Add one integration entry **per grow space** (tent, room, or zone). The setup
flow walks you through:

1. Grow-space name and type.
2. Mapping sensor and control entities (all mappings are optional). You can also
   enable Tuya cloud polling here.
3. AI health options (check interval, critical-score threshold, optional notify
   service, result retention).
4. AI provider selection (`None`, `Gemini`, `OpenAI`, or `Ollama`).
5. Provider credentials/endpoint.
6. Model selection from discovered models (with a manual fallback).

See [Configuration](configuration.md) for a detailed walkthrough of every step
and field.

!!! tip "To enable AI vision checks"
    Map a `camera` entity and select a vision-capable provider and model. Checks
    then run on a schedule, on demand from the run button, or via the
    `tendrilgrow.run_ai_health_check` service.
