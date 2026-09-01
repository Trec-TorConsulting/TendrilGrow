# Entities

TendrilGrow creates entities **per grow space**, attached to that space’s
device. Names follow Home Assistant `has_entity_name` rules, so IDs are usually
`<domain>.<grow_space_slug>_<entity_slug>`.

**Example** grow space title `4x4 Flower`:

| Helper | Example entity ID |
| --- | --- |
| Growth Stage | `select.4x4_flower_growth_stage` |
| Stage Started | `date.4x4_flower_stage_started` |
| Week In Stage | `sensor.4x4_flower_week_in_stage` |
| Flush Now | `button.4x4_flower_flush_now` |
| AI Health Score | `sensor.4x4_flower_ai_health_score` |

If you renamed the device later, **old** entities keep their original IDs.
Always copy IDs from the device page. Stage Started / Week In Stage are forced
to the **Growth Stage** prefix (see [Upgrading](upgrade.md#upgrade-033)).

## Cultivation context (always created)

Editable helpers that ground the AI advisor. See [Cultivation plan](cultivation.md).

**Select**

- **Growth Stage** — `seedling`, `mother`, `clone`, `vegetative`,
  `early_flower`, `mid_flower`, `late_flower`, `flush`, `harvest`, `dry`,
  `cure`, `ready` (default `vegetative`).
- **Water Type** — `tap`, `ro`, `filtered`, `bottled`, `rain`, `well`,
  `distilled`, `spring`, `mixed` (default `tap`).

**Date**

- **Stage Started** — calendar date the current stage began. Changing Growth
  Stage resets this to today; backdate if needed. Old Week In Stage numbers
  convert on upgrade (week 2 → about 14 days ago).

**Computed**

- **Week In Stage** — days since Stage Started ÷ 7 (one decimal). Not editable.

**Numbers**

- Sites / Plants
- Total System Volume (gal)
- Target pH
- Target EC (mS/cm)
- Feed Interval (days)
- Lights On (hours)
- Runoff Target (%)
- Electricity Price (per kWh)

**Text**

- Strain / Genetics
- Nutrient Line
- Base Nutrients
- Additives

## Derived sensors

- **VPD** (kPa) — mapped air temperature + humidity. Created when both air
  roles exist.
- **Dew Point** (°C) — same inputs.
- **DLI** (mol/m²/day, estimated) — mapped PPFD × Lights On hours.
- **Stage Projection** — days remaining in the current stage; attributes for
  projected stage-end, harvest, and ready dates.

## Camera timelapse (always created)

- **Capture Timelapse Frame** (button)
- **Timelapse Frames** (sensor) — count; attributes include capture directory
  and `/local` URL when under `/config/www`
- **Timelapse Last Frame** (timestamp)

Scheduled capture is off until you enable it in Options. Allow-list:
[Installation](installation.md#allow-list-for-timelapse-optional).

## Calendar

- **Grow Timeline** — projected stage-end, harvest, ready, and next flush due.

## Tasks

- **Grow Tasks** — flush due, stage change approaching, critical AI alert.

## AI health (when AI is fully configured)

Requires camera + provider ≠ None + vision model. See [AI health](ai-health.md).

- **AI Health Score** (0–100) — `report` and `feeding_schedule_md` attributes
  drive the markdown cards
- **AI Health Summary**
- **AI Last Health Check** (timestamp, diagnostic)
- **AI Health Critical Alert** (binary sensor, problem)
- **AI Weekly Journal**
- **Run AI Health Check** (button)

## Reservoir flush (always created)

- **Flush Now** (button)
- **Flush Interval** (number, default 7 days)
- **Last Flush**, **Days Since Flush**, **Days Until Flush**, **Next Flush Due**
- **Flush Due** (binary sensor, problem)

See [Flush tracking](flush-tracking.md).

## Pumps (per mapped pump)

- One **switch** per `rdwc_pump`, `chiller_pump`, `air_pump`
- Per-pump **Power** (mapped or discovered)
- **Total Pump Power**
- **Pump Daily Cost** (24 h × Electricity Price)

See [Pumps](pumps.md).

## Water sensors

**Preferred:** bind LocalTuya / Tuya Local; auto-map pH, EC, CF, TDS, ORP,
water temperature. Canopy air stays operator-mapped.

**Cloud fallback** (no local device, polling enabled): per-device pH, EC, CF,
TDS, ORP, water temperature, probe ambient humidity, battery, last updated.

See [Tuya / LocalTuya](tuya-water.md).
