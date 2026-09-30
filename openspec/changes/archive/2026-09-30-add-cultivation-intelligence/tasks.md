# Tasks: add-cultivation-intelligence

## 1. Constants, Configuration & Domain Models

- [x] 1.1 Add `SENSOR_ROLE_LEAF_TEMPERATURE = "leaf_temperature"` and `SENSOR_ROLE_WATER_LEVEL = "water_level"` to `const.py`
- [x] 1.2 Add `CONF_LEAF_TEMP_OFFSET = "leaf_temp_offset"` and default `-3.0` (°F) / `-1.67` (°C) to `const.py`
- [x] 1.3 Add diagnostic status enums/constants for reservoir drift (`DRIFT_EQUILIBRIUM`, `DRIFT_DILUTE`, `DRIFT_FEED`, `DRIFT_ROOT_CHECK`) to `const.py`
- [x] 1.4 Update `GrowSpace` model in `models/grow.py` to support `leaf_temperature` and `water_level` sensor mappings

## 2. Pure Mathematical Insights & Tests

- [x] 2.1 Implement `compute_leaf_vpd_kpa` in `insights.py` supporting leaf temp or ambient air + offset
- [x] 2.2 Implement `compute_dew_point_margin` in `insights.py`
- [x] 2.3 Implement `diagnose_reservoir_drift` in `insights.py` with slope analysis and root health plunge detection
- [x] 2.4 Implement `compute_transpiration_rate` and stalled consumption detection in `insights.py`
- [x] 2.5 Implement `compute_days_since_flip` in `insights.py`
- [x] 2.6 Write comprehensive unit tests in `tests/test_insights.py` covering all edge cases, thresholds, and units

## 3. Sensors and Binary Sensor Entities

- [x] 3.1 Implement `TendrilGrowReservoirDriftSensor` in `sensors/environment.py` with 24h rolling buffer and drift state
- [x] 3.2 Implement `TendrilGrowLeafVpdSensor` in `sensors/environment.py` with IR probe or offset fallback
- [x] 3.3 Implement `TendrilGrowDewPointMarginSensor` in `sensors/environment.py`
- [x] 3.4 Implement `TendrilGrowPhotoperiodSensor` and `TendrilGrowDaysSinceFlipSensor` in `sensors/stage.py` or `sensors/environment.py`
- [x] 3.5 Implement `TendrilGrowTranspirationRateSensor` in `sensors/environment.py`
- [x] 3.6 Implement `TendrilGrowMoldRiskBinarySensor` in `binary_sensor.py` with stage-aware thresholds
- [x] 3.7 Register all new sensor and binary sensor classes in `sensor.py` and `binary_sensor.py`

## 4. 60/60 Harvest Drying/Curing Targets & Stage Transitions

- [x] 4.1 Update `STAGE_TARGETS` in `const.py` with 60/60 target bands (VPD `0.65-0.78`) for `dry` and `cure` stages
- [x] 4.2 Update `STAGE_OBJECTIVES` in `const.py` with 60/60 curing guidance and terpene preservation instructions for the AI advisor
- [x] 4.3 Ensure `grow_targets.py` seeds default VPD targets when switching to `dry` or `cure`
- [x] 4.4 Add unit tests for `dry` and `cure` target seeding in `tests/test_grow_targets.py`

## 5. UI Config Flows & Translations

- [x] 5.1 Expose `leaf_temperature` and `water_level` in sensor selection steps in `config_flow.py`
- [x] 5.2 Expose `CONF_LEAF_TEMP_OFFSET` in options flow in `config_flow.py` and `entry_config.py`
- [x] 5.3 Add English translations in `strings.json` and `translations/en.json` for all new sensor roles, config options, diagnostic states, and sensors

## 6. Verification, Quality Checks & Live HA Validation

- [x] 6.1 Run test suite (`pytest`) and ensure 100% test pass
- [x] 6.2 Run code quality linters (`ruff check .` and `ruff format --check .`)
- [x] 6.3 Validate OpenSpec change with `openspec validate add-cultivation-intelligence --type change`
- [x] 6.4 Update live HA validation script `scripts/validate_live_ha.py` to audit new intelligence entities
- [x] 6.5 Deploy and verify live on Home Assistant (`http://192.168.4.20:8123`)
