<p align="center">
  <img src="assets/logo.svg" alt="TendrilGrow" width="460">
</p>

# TendrilGrow

TendrilGrow is a [Home Assistant](https://www.home-assistant.io/) custom
integration for indoor cultivation. Install it from
[HACS](https://hacs.xyz/), add **one config entry per grow space**, and map the
sensors and cameras you already have. No hardcoded entity IDs.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Trec-TorConsulting&repository=TendrilGrow&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tendrilgrow)

## Start here

1. [Install via HACS](installation.md) (restart Home Assistant after download).
2. Walk through a complete [4×4 RDWC example](quick-start.md).
3. Fill [Cultivation Plan](cultivation.md) (Growth Stage + Stage Started date).
4. Optionally enable [AI health checks](ai-health.md) with a camera.

## What you get

- **Per-space device** — helpers, chemistry, pumps, flush cadence, and AI on
  one Home Assistant device.
- **Cultivation clock** — Stage Started is a date; Week In Stage is computed
  from it (feeds AI dosing and harvest projections).
- **Reservoir chemistry** — prefer LocalTuya / Tuya Local on LAN; cloud Tuya
  OpenAPI is fallback-only.
- **Derived climate** — VPD, dew point, estimated DLI from canopy air + PPFD.
- **Pumps** — RDWC / chiller / air switches, power, estimated daily cost.
- **Flush tracking** — Flush Now, interval, days-until, overdue reminder.
- **AI advisor** — quality-first score, issues, mix-order feeding markdown,
  live vs sterile reservoir rules.
- **Timeline and tasks** — calendar events and a to-do list for flush / stage /
  critical health.

Control is **manual and opt-in**. TendrilGrow does not turn pumps or lights by
itself.

## Guides

<div class="grid cards" markdown>

-   **[Installation](installation.md)**

    ---

    HACS custom repository, manual zip, and first add-integration.

-   **[Quick start](quick-start.md)**

    ---

    Named example tent with mappings, helpers, and a Lovelace card.

-   **[Configuration](configuration.md)**

    ---

    Every config-flow and options field.

-   **[Examples](examples.md)**

    ---

    Copy-paste automations, dashboard YAML, and `configuration.yaml`.

-   **[Troubleshooting](troubleshooting.md)**

    ---

    Missing AI entities, VPD, LocalTuya, Entity not found.

-   **[FAQ](faq.md)**

    ---

    Multiple tents, cost, internet, what is automated.

</div>

## Project

- **Distribution:** HACS custom integration
- **Minimum Home Assistant:** 2026.2.0
- **Current version:** see [Changelog](changelog.md)
- **License:** [MIT](https://github.com/Trec-TorConsulting/TendrilGrow/blob/main/LICENSE)

!!! note "Decision support, not a safety system"
    TendrilGrow assists monitoring and agronomy advice. It does not replace
    safe electrical, environmental, or horticultural practice. Validate
    automations and control actions before you rely on them.
