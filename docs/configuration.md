# Configuration

TendrilGrow uses one Home Assistant config entry **per grow space**. Each entry
owns mappings, AI credentials, and helper entities for that tent or room.

Re-open settings anytime:
**Settings → Devices & Services → TendrilGrow → Configure** (options flow).

## Config flow

| Step | What you do |
| --- | --- |
| **Create grow space** | Name, grow type, size/descriptor. |
| **Map entities** | Optional LocalTuya/Tuya Local device, HA sensors/controls, optional cloud Tuya fallback, AI interval, timelapse. |
| **AI provider** | `None`, `Gemini`, `OpenAI`, or `Ollama`. |
| **Provider credentials** | API key and/or endpoint. |
| **Choose model** | Pick a discovered **vision** model, or type a name if discovery fails. |

A worked example with values: [Quick start](quick-start.md).

## Grow type

Dropdown plus custom text:

`rdwc`, `dwc`, `aeroponic`, `soil`, `coco`, `other` — or e.g. `Clone King`.

Grow type feeds live vs sterile chemistry rules for RDWC/DWC
([AI health](ai-health.md#live-vs-sterile-reservoirs)).

## Sensor roles

All optional. Map only what exists.

| Role | UI label | Maps to |
| --- | --- | --- |
| `temperature` | Air temperature sensor (canopy, used for VPD) | Tent air, **not** reservoir |
| `humidity` | Air humidity sensor (canopy, used for VPD) | Tent RH |
| `water_temperature` | Water/reservoir temperature sensor | Probe in the mix |
| `light_ppfd` | PPFD/light sensor | For estimated DLI |
| `ph` / `ec` / `cf` / `orp` / `tds` | Reservoir chemistry | Auto-filled if you bind a local water monitor |
| `camera` | Camera entity | Required for AI vision |
| `rdwc_pump_power` / `chiller_pump_power` / `air_pump_power` | Optional W sensors | Else auto-discovery |

!!! warning "Air vs water temperature"
    If the reservoir probe is mapped as canopy air, **VPD will be wrong**.

## Control roles

| Role | UI label |
| --- | --- |
| `lights` | Lights control |
| `fans` | Fans control |
| `inline_fans` | Inline fans control |
| `rdwc_pump` | RDWC circulation pump (run before header-bucket dosing) |
| `chiller_pump` | Chiller pump (optional) |
| `air_pump` | Air pump (optional) |

See [Pumps](pumps.md).

## AI health settings

| Setting | Default | Meaning |
| --- | --- | --- |
| Check interval (hours) | `12` | Scheduled vision checks |
| Critical score threshold | `20` | At or below → critical alert |
| Notify service | _none_ | Optional `notify.*` |
| Result retention (days) | `30` | History window |

See [AI health checks](ai-health.md).

## Camera timelapse settings

| Setting | Default | Meaning |
| --- | --- | --- |
| Timelapse enabled | `false` | Periodic snapshots |
| Capture interval (hours) | `24` | Schedule |
| Frame retention | `120` | Oldest pruned first |
| Capture directory override | empty | Optional path |

Default directory:
`/config/www/tendrilgrow/<grow_slug>/timelapse/`.

The path must be in `homeassistant.allowlist_external_dirs` or captures pause
and a Repair issue is raised ([Installation](installation.md#allow-list-for-timelapse-optional)).

## Water monitoring

Prefer **Local water monitor** (LocalTuya or Tuya Local device). TendrilGrow
auto-maps pH, EC, CF, ORP, TDS, and water temperature and **does not** call
Tuya OpenAPI while that device is bound.

Cloud polling (access ID/secret, region, device IDs, interval default **600** s)
is fallback-only. See [Tuya / LocalTuya](tuya-water.md).

Still map **canopy** air temp/humidity yourself for VPD.

## Cultivation context

Helpers are created for every grow space (Growth Stage, Stage Started, Week In
Stage, water type, volumes, targets, nutrient text). They are not part of the
config flow — edit them on the device or a dashboard.

See [Cultivation plan](cultivation.md) and [Entities](entities.md).
