# Proposal: add-air-climate-vpd

## Why

Vapor Pressure Deficit (VPD) is a canopy/air metric — it must be computed from the
**air** temperature and **air** relative humidity around the plants, in Celsius.
Two shipped defects broke this:

1. **Wrong source.** Tuya auto-mapped its **water/reservoir** temperature onto the
   generic `temperature` role, so any VPD (and the AI prompt's temperature line)
   used reservoir water temperature instead of canopy air.
2. **No unit handling.** Readings arrive in the operator's Home Assistant unit
   system (here, °F). The VPD math assumed °C, so a 65 °F reading was treated as
   65 °C, producing absurd values.

In addition, the model claimed to expose VPD but never actually surfaced a VPD
entity — the helper was only exercised by tests. This change makes VPD correct and
real, and lets operators map their canopy air probes even when Tuya is enabled.

## What Changes

- Add a dedicated **`water_temperature`** sensor role; Tuya's water temperature
  auto-maps to it instead of the air `temperature` role. `temperature`/`humidity`
  are now unambiguously **air (canopy)** roles used for VPD.
- Make **air temperature** and **air humidity** mappable in the options flow **even
  when Tuya is enabled** (Tuya supplies water metrics, not canopy air).
- Add **unit-aware** VPD helpers (`GrowSpace.to_celsius`, `compute_vpd_kpa`) that
  convert °F→°C before computing.
- **Expose a VPD sensor** (kPa) per grow space, computed from the mapped air temp +
  air humidity, reporting unavailable when inputs are missing/invalid.
- Improve the **AI prompt**: label each metric with its unit, separate air vs water
  temperature, and include the derived VPD line.
- Update i18n labels and the live validator (unit-aware VPD, water-temp reporting).

## Capabilities

### Modified Capabilities
- `grow-data-model`: `temperature`/`humidity` are air roles; add a `water_temperature`
  role; derived VPD is unit-aware, computed from air temp + air humidity, and exposed
  as a sensor.

## Impact

- **Code**: `const.py` (roles), `models/grow.py` (unit-aware helpers), `sensor.py`
  (Tuya remap + VPD sensor), `ai/health_checks.py` (unit-aware, labeled prompt +
  VPD), `strings.json`/`translations/en.json`, `scripts/validate_live_ha.py`, tests.
- **Migration**: existing Tuya entries stop auto-filling the air `temperature` role;
  operators map their canopy air temp/RH (e.g., an AC-Infinity-style controller's
  inside sensors) in options. Water temperature remains available via the new role.
- **No breaking API**: additive roles/entity; VPD is unavailable until air temp +
  air humidity are mapped.
