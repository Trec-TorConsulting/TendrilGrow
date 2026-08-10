# Configuration

TendrilGrow uses one Home Assistant config entry **per grow space**. Each entry
owns its own equipment, mappings, targets, schedules, and AI provider.

## Config flow (initial setup)

The onboarding flow has the following steps:

| Step | Purpose |
| --- | --- |
| **Create grow space** | Name, grow type, and size/descriptor. |
| **Map entities** | Map your Home Assistant entities to grow roles; optionally enable Tuya. |
| **AI provider** | Choose `None`, `Gemini`, `OpenAI`, or `Ollama`. |
| **Provider credentials** | Enter the API key or endpoint for the chosen provider. |
| **Choose model** | Pick a discovered model (or enter one manually if discovery fails). |

You can re-run mapping and settings at any time from the **Options** flow
(**Settings → Devices & Services → TendrilGrow → Configure**).

## Grow type

The grow type is a preset dropdown that also accepts a custom value:

`rdwc`, `dwc`, `aeroponic`, `soil`, `coco`, `other` — or type your own (for
example, a specific cloner model).

## Sensor roles

All sensor mappings are optional. Map only what you have.

| Role | Description |
| --- | --- |
| `temperature` | **Air** temperature (canopy) — used for VPD. |
| `humidity` | **Air** humidity (canopy) — used for VPD. |
| `water_temperature` | Water/reservoir temperature probe. |
| `light_ppfd` | PPFD/light sensor. |
| `ph` | Reservoir pH. |
| `ec` | Reservoir EC. |
| `cf` | Reservoir CF. |
| `orp` | Reservoir ORP. |
| `tds` | Reservoir TDS. |
| `camera` | Camera entity (required for AI vision checks). |
| `rdwc_pump_power` | Optional explicit power sensor for the RDWC pump. |
| `chiller_pump_power` | Optional explicit power sensor for the chiller pump. |
| `air_pump_power` | Optional explicit power sensor for the air pump. |

!!! warning "Air vs. water temperature"
    `temperature`/`humidity` are the **canopy air** roles used for VPD.
    Reservoir temperature is a separate `water_temperature` role. If you map a
    water probe into the air role, VPD will be wrong.

## Control roles

| Role | Description |
| --- | --- |
| `lights` | Grow lights. |
| `fans` | Circulation fans. |
| `inline_fans` | Inline/exhaust fans. |
| `rdwc_pump` | RDWC circulation pump (run before any header-bucket dosing). |
| `chiller_pump` | Chiller pump (optional). |
| `air_pump` | Air pump (optional). |

See [Pump control and monitoring](pumps.md) for the pump switches, power
sensors, and the `set_pump` service.

## AI health settings

| Setting | Default | Meaning |
| --- | --- | --- |
| Check interval (hours) | `12` | How often scheduled checks run. |
| Critical score threshold | `20` | Scores at or below this trigger a critical alert. |
| Notify service | _none_ | Optional `notify.*` service for critical alerts. |
| Result retention (days) | `30` | How long health-check history is kept. |

See [AI health checks](ai-health.md) for provider details and scoring.

## Camera timelapse settings

| Setting | Default | Meaning |
| --- | --- | --- |
| Timelapse enabled | `false` | Turns periodic camera frame capture on/off. |
| Capture interval (hours) | `24` | How often scheduled frame capture runs. |
| Frame retention | `120` | Max frames kept per grow space (oldest pruned first). |
| Capture directory override | _empty_ | Optional absolute/relative path override for frame storage. |

Default frame directory:
`/config/www/tendrilgrow/<grow_slug>/timelapse/`.

!!! warning "One-time Home Assistant allow-list step"
    Snapshot writes require the target directory in
    `homeassistant.allowlist_external_dirs`. If missing, TendrilGrow raises a
    Repair issue and pauses scheduled captures until the path is allow-listed
    and one capture succeeds.

## Tuya cloud water monitoring (optional)

Enable Tuya during the **Map entities** step to poll reservoir water monitors
from the Tuya cloud. You will provide:

- Access ID and access secret
- Region
- Optional user UID
- Device IDs (comma-separated)
- Poll interval (seconds; default **600**)

When enabled, water-quality sensors are created and **auto-mapped** into the
matching sensor roles. You still map the **air** temperature/humidity and camera
yourself. See [Tuya water monitoring](tuya-water.md).

## Cultivation context

TendrilGrow exposes editable helper entities (growth stage, strain, week in
stage, reservoir volume, targets, and more) that ground the AI advisor. See
[Entities](entities.md) for the full list.
