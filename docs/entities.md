# Entities

TendrilGrow creates entities per grow space, attached to that space's device.
Which entities appear depends on what you mapped and enabled. This reference
lists the entities and the conditions under which they are created.

## Cultivation context (always created)

Editable helpers that ground the AI advisor. Set them to match your grow.

**Select**

- Growth Stage — one of: `seedling`, `mother`, `clone`, `vegetative`,
  `early_flower`, `mid_flower`, `late_flower`, `flush`, `harvest`, `dry`, `cure`,
  `ready` (default `vegetative`).
- Water Type — makeup water for fills/flushes: `tap`, `ro`, `filtered`,
  `bottled`, `rain`, `well`, `distilled`, `spring`, `mixed` (default `tap`).

**Date**

- Stage Started — the calendar date the current stage began. Changing Growth
  Stage resets this to today; you can backdate it. Existing Week In Stage
  numbers are converted on upgrade (week 2 → about 14 days ago).

**Computed**

- Week In Stage — days since Stage Started ÷ 7 (one decimal). Used by the AI
  advisor and stage-projection math.

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

- **VPD** (kPa) — computed from the mapped air temperature and humidity. Created
  when both air roles are available.
- **Dew Point** (°C) — from the mapped air temperature and humidity.
- **DLI** (mol/m²/day, estimated) — from the mapped PPFD and the configured
  photoperiod (Lights On).
- **Stage Projection** — days remaining in the current stage plus projected
  stage-end, harvest, and ready dates.

## Camera timelapse status (always created)

- **Capture Timelapse Frame** (button) — captures one frame immediately.
- **Timelapse Frames** (sensor) — count of stored frames.
  Attributes: capture directory, `/local` URL base (when under `/config/www`),
  latest frame file path, latest frame URL.
- **Timelapse Last Frame** (sensor, timestamp) — newest captured frame time.

## Calendar

- **Grow Timeline** (calendar) — projected stage-end, harvest, and ready dates
  plus the next reservoir flush due date, surfaced as calendar events.

## Tasks

- **Grow Tasks** (to-do list) — auto-generated actionable tasks: reservoir flush
  due, stage change approaching, and a critical AI health alert.

## AI health (created when AI is configured)

- **AI Health Score** (0–100)
- **AI Health Summary**
- **AI Feeding Schedule**
- **AI Last Health Check** (timestamp, diagnostic)
- **AI Health Critical Alert** (binary sensor, problem class)
- **AI Weekly Journal** (7-day recap composed from recorded checks)
- **Run AI Health Check** (button)

## Reservoir flush tracking (always created)

- **Flush Now** (button)
- **Flush Interval** (number, default 7 days)
- **Last Flush** (sensor)
- **Days Since Flush** (sensor)
- **Days Until Flush** (sensor)
- **Next Flush Due** (sensor)
- **Flush Due** (binary sensor, problem class)

## Pumps (created per mapped pump)

- One **switch** per mapped pump (`rdwc_pump`, `chiller_pump`, `air_pump`).
- One **Power** sensor per pump (from an explicit power mapping or auto-discovery).
- **Total Pump Power** (sensor).
- **Pump Daily Cost** (estimated) — total pump power over 24 h × the Electricity
  Price helper, in your Home Assistant currency.

## Water sensors

**Preferred:** bind a LocalTuya / Tuya Local device; TendrilGrow auto-maps its
pH, EC, CF, TDS, ORP, and water-temperature entities onto grow-space roles
(canopy air temp/humidity stay operator-mapped for VPD).

**Cloud fallback** (only when no local device is bound and cloud polling is
enabled): TendrilGrow creates per-device sensors as reported and normalized:

- pH, EC, CF, TDS, ORP
- Water Temperature
- Humidity (probe ambient; not canopy RH)
- Battery
- Last Updated (diagnostic)

!!! tip "Entity naming"
    Entities use Home Assistant's per-device naming, so their IDs are prefixed
    with the grow-space name (for example, `sensor.<grow_space>_ai_health_score`).
