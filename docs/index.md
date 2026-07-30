# TendrilGrow

TendrilGrow is a [Home Assistant](https://www.home-assistant.io/) custom
integration for indoor cultivation. It unifies grow-space configuration,
sensor and control mapping, optional Tuya cloud water monitoring, and
camera-based AI health checks into a single [HACS](https://hacs.xyz/)-installable
package.

/ One config entry per grow space. No hardcoded entity IDs. Bring your own
sensors, controllers, cameras, and AI provider. /

## Highlights

- **Per-grow-space model** — one config entry per tent, room, or zone, each with
  its own sites, mappings, targets, and schedules.
- **Flexible role mapping** — air temperature/humidity (canopy, for VPD), a
  distinct water/reservoir temperature, light (PPFD), pH, EC, CF, ORP, TDS,
  cameras, plus lights, fans, and inline fans.
- **Derived VPD** — unit-aware (°F → °C) vapor-pressure-deficit sensor computed
  from the mapped air temperature and humidity.
- **Pump control and monitoring** — toggle RDWC, chiller, and air pumps from the
  dashboard or automations, with real-time per-pump and total power tracking.
- **Reservoir flush tracking** — one-press "Flush Now", editable interval, and
  days-since / days-until / next-due sensors with an overdue reminder.
- **Optional Tuya cloud water monitoring** — signed OpenAPI polling, datapoint
  normalization, per-device sensors, and automatic sensor-role mapping.
- **Camera-based AI health checks** — quality-first agronomy scoring,
  observations, issues, recommended actions, and a dynamic feeding schedule.
- **Pluggable AI providers** — Google Gemini, OpenAI, or Ollama, with dynamic
  model discovery after credentials are entered.
- **Secrets-safe** — API keys and Tuya secrets are redacted in diagnostics and
  logs.

## Where to next

<div class="grid cards" markdown>

- **[Installation](installation.md)** — install via HACS and complete first-time
  setup.
- **[Configuration](configuration.md)** — the config and options flows, roles,
  and settings.
- **[AI health checks](ai-health.md)** — providers, scoring, scheduling, and
  notifications.
- **[Services](services.md)** — every service and its fields.
- **[Troubleshooting](troubleshooting.md)** — common issues and fixes.
- **[FAQ](faq.md)** — frequently asked questions.

</div>

## Project status

- **Maturity:** foundation release (actively developed)
- **Distribution:** HACS custom integration
- **Minimum Home Assistant:** 2026.2.0
- **License:** [MIT](https://github.com/Trec-TorConsulting/TendrilGrow/blob/main/LICENSE)

!!! note "Decision support, not a safety system"
    TendrilGrow assists monitoring and decision support. It does not replace safe
    electrical, environmental, or horticultural practices. Validate automations
    and control actions before production use.
