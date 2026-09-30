# Proposal: add-cultivation-intelligence

## Why

Indoor cannabis cultivation, especially in Recirculating Deep Water Culture (RDWC), relies on tightly coupled biological dynamics that simple static sensor readings cannot capture. In RDWC, the rolling relationship between Electrical Conductivity (EC) and pH reveals whether plants are absorbing balanced nutrients (`equilibrium`), transpiring water faster than ions (`dilute_recommended`), or consuming nutrients rapidly (`feed_recommended`). Sudden unbuffered pH crashes indicate anaerobic root infection or Pythium well before foliar symptoms appear.

Furthermore, air VPD overlooks the true leaf boundary layer because high-efficiency LED fixtures lack infrared heat radiation; powdery mildew and Botrytis (bud rot) germinate when dew point margin shrinks; photoperiod flip to 12/12 governs flowering senescence; stalled daily water consumption signals root disease; and harvest drying/curing requires strict adherence to the 60°F / 60% RH gold standard to preserve volatile terpenes.

TendrilGrow currently lacks these critical biological and environmental intelligence metrics. Adding them provides growers with automated diagnostic clarity, early disease warnings, and stage-tuned precision.

## What Changes

- **RDWC EC vs. pH Drift Diagnostic Engine**: Add rolling slope analysis of EC and pH over a 12h–24h window; classify into `equilibrium`, `dilute_recommended`, `feed_recommended`, and `root_health_check`. Expose `sensor.<grow>_reservoir_drift_diagnosis`.
- **Leaf Surface Temperature (IR) & True Leaf VPD**: Support optional mapped infrared leaf temperature sensor (`SENSOR_ROLE_LEAF_TEMPERATURE`) or configurable LED leaf temperature offset (`CONF_LEAF_TEMP_OFFSET`, default `-3.0°F` / `-1.67°C`). Expose `sensor.<grow>_leaf_vpd`.
- **Powdery Mildew & Botrytis Risk Index**: Calculate dew point margin ($T_{leaf/air} - T_{dew}$); expose `sensor.<grow>_dew_point_margin` and `binary_sensor.<grow>_mold_risk` (flags when margin < 2.0°C / 3.6°F or RH > 65% in mid/late flower, dry, and cure).
- **Photoperiod & 12/12 Flip Tracking**: Expose `sensor.<grow>_photoperiod_hours` and auto-compute `sensor.<grow>_days_since_flip` when in flowering stages, feeding into dynamic Daily Light Integral (DLI) estimations.
- **Reservoir Water Level & Daily Transpiration Tracking**: Add `SENSOR_ROLE_WATER_LEVEL` to entity mapping; expose `sensor.<grow>_transpiration_rate_daily` and detect stalled water uptake as an early hypoxia/root rot warning.
- **Harvest Drying & Curing Phase (60/60 Rule)**: Seed default target bands in `dry` and `cure` stages to 60°F ± 2°F (15.5°C) and 60% RH ± 3% (VPD 0.65–0.78 kPa), and update AI advisor objectives for terpene preservation.

## Capabilities

### New Capabilities
- `cultivation-intelligence`: Advanced RDWC reservoir drift diagnosis, true leaf VPD, dew point margin, mold risk binary sensor, photoperiod and 12/12 flip tracking, and daily transpiration consumption rate.

### Modified Capabilities
- `grow-target-schedule`: Seed target climate and VPD bands for `dry` and `cure` stages adhering to the 60/60 drying and curing standard.

## Impact

- **New Sensor Entities**: `TendrilGrowReservoirDriftSensor`, `TendrilGrowLeafVpdSensor`, `TendrilGrowDewPointMarginSensor`, `TendrilGrowPhotoperiodSensor`, `TendrilGrowDaysSinceFlipSensor`, `TendrilGrowTranspirationRateSensor`.
- **New Binary Sensor Entity**: `TendrilGrowMoldRiskBinarySensor` (`problem` device class).
- **Domain Math**: Add leaf VPD, dew point margin, drift diagnostic regression, and transpiration rate helpers to `insights.py`.
- **Config Flow & Options**: Add `SENSOR_ROLE_LEAF_TEMPERATURE` and `SENSOR_ROLE_WATER_LEVEL` to sensor selector forms; add `CONF_LEAF_TEMP_OFFSET` to options.
- **Constants**: Add new sensor roles, config keys, and target ranges in `const.py`.
- **Translations**: Add localized labels and descriptions for all new diagnostic sensors, binary sensors, and configuration keys.
