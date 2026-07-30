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

**Numbers**

- Week In Stage
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

## Calendar

- **Grow Timeline** (calendar) — projected stage-end, harvest, and ready dates
  plus the next reservoir flush due date, surfaced as calendar events.

## AI health (created when AI is configured)

- **AI Health Score** (0–100)
- **AI Health Summary**
- **AI Feeding Schedule**
- **AI Last Health Check** (timestamp, diagnostic)
- **AI Health Critical Alert** (binary sensor, problem class)
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

## Tuya water sensors (created when Tuya is enabled)

Per device, as reported and normalized:

- pH, EC, CF, TDS, ORP
- Water Temperature
- Humidity
- Battery
- Last Updated (diagnostic)

!!! tip "Entity naming"
    Entities use Home Assistant's per-device naming, so their IDs are prefixed
    with the grow-space name (for example, `sensor.<grow_space>_ai_health_score`).
