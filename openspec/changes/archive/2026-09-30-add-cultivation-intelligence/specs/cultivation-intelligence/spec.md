# cultivation-intelligence Specification

## ADDED Requirements

### Requirement: RDWC Reservoir Drift Diagnosis
The integration SHALL provide a reservoir drift diagnostic sensor (`sensor.<grow>_reservoir_drift_diagnosis`) that evaluates the rolling trend of Electrical Conductivity (EC) and pH over a rolling 12h–24h window. When EC rises and pH falls beyond threshold limits, it MUST report `dilute_recommended`. When EC falls and pH rises beyond threshold limits, it MUST report `feed_recommended`. When pH plunges below 5.2 or drops rapidly while EC is steady or rising, it MUST report `root_health_check`. When trends are within nominal stability bounds, it MUST report `equilibrium`.

#### Scenario: Transpiration outstrips feeding
- **WHEN** 24-hour EC increases by $\ge 0.10\text{ mS/cm}$ and pH decreases by $\ge 0.2$
- **THEN** the drift diagnosis sensor state is `dilute_recommended`

#### Scenario: Plant consumes nutrients heavily
- **WHEN** 24-hour EC decreases by $\ge 0.10\text{ mS/cm}$ and pH increases by $\ge 0.2$
- **THEN** the drift diagnosis sensor state is `feed_recommended`

#### Scenario: Anaerobic root pathogen acid plunge
- **WHEN** reservoir pH drops below 5.2 or falls by $\ge 0.40$ in 24 hours while EC is non-decreasing
- **THEN** the drift diagnosis sensor state is `root_health_check`

#### Scenario: Stable nutrient solution
- **WHEN** EC and pH changes over 24 hours remain within $\pm 0.1\text{ mS/cm}$ and $\pm 0.2\text{ pH}$
- **THEN** the drift diagnosis sensor state is `equilibrium`

### Requirement: Leaf Surface Temperature and True Leaf VPD
The integration SHALL expose a true Leaf VPD sensor (`sensor.<grow>_leaf_vpd`) in kPa. If an infrared leaf temperature sensor is mapped (`SENSOR_ROLE_LEAF_TEMPERATURE`), the integration MUST use its measured temperature. If unmapped, the integration MUST derive leaf temperature by subtracting the configured leaf temperature offset (`CONF_LEAF_TEMP_OFFSET`, default `-3.0°F` / `-1.67°C`) from the ambient air temperature.

#### Scenario: Leaf temperature sensor mapped
- **WHEN** a leaf temperature sensor is mapped and reports 22.0°C while air is 24.0°C and RH is 60%
- **THEN** the Leaf VPD sensor calculates saturation vapor pressure using 22.0°C

#### Scenario: Leaf temperature offset used as fallback
- **WHEN** no leaf temperature sensor is mapped, air temperature is 77.0°F (25.0°C), RH is 55%, and default offset of -3.0°F is configured
- **THEN** the Leaf VPD sensor calculates VPD using leaf temperature of 74.0°F (23.33°C)

### Requirement: Dew Point Margin and Mold Risk Binary Sensor
The integration SHALL expose a Dew Point Margin sensor (`sensor.<grow>_dew_point_margin`) reporting the difference between canopy/air temperature and dew point. The integration SHALL expose a problem binary sensor (`binary_sensor.<grow>_mold_risk`) that turns `on` when dew point margin is $\le 2.0^\circ\text{C}$ ($3.6^\circ\text{F}$) or when relative humidity is $\ge 65\%$ during `mid_flower`, `late_flower`, `dry`, or `cure` stages.

#### Scenario: Dew point margin reaches condensation threshold
- **WHEN** canopy temperature is within 1.5°C of the calculated dew point
- **THEN** `sensor.<grow>_dew_point_margin` reports 1.5°C and `binary_sensor.<grow>_mold_risk` is `on`

#### Scenario: High humidity in late flower triggers mold risk
- **WHEN** relative humidity is 68% and the grow stage is `late_flower`
- **THEN** `binary_sensor.<grow>_mold_risk` is `on` with an attribute indicating humidity risk

#### Scenario: Safe vegetative climate
- **WHEN** relative humidity is 65%, dew point margin is 4.5°C, and grow stage is `vegetative`
- **THEN** `binary_sensor.<grow>_mold_risk` is `off`

### Requirement: Photoperiod and Days Since Flip Tracking
The integration SHALL expose a photoperiod duration sensor (`sensor.<grow>_photoperiod_hours`) and a days since flip sensor (`sensor.<grow>_days_since_flip`). When the grow space is in a flowering stage (`early_flower`, `mid_flower`, `late_flower`), `sensor.<grow>_days_since_flip` MUST report elapsed days since the flowering stage start date. For non-flowering stages, it MUST report `None` / unavailable.

#### Scenario: Active flower tracking
- **WHEN** a space is in `mid_flower` with a stage start date 21 days ago
- **THEN** `sensor.<grow>_days_since_flip` reports 21

#### Scenario: Vegetative stage has no flip count
- **WHEN** a space is in `vegetative`
- **THEN** `sensor.<grow>_days_since_flip` is unavailable or `None`

### Requirement: Reservoir Water Level and Transpiration Tracking
The integration SHALL support mapping a water level sensor (`SENSOR_ROLE_WATER_LEVEL`) and expose daily transpiration rate (`sensor.<grow>_transpiration_rate_daily`). When water level consumption stalls over a 24-hour illuminated period during vegetative or flowering stages, the sensor MUST flag `stalled_consumption` in its attributes.

#### Scenario: Normal daily transpiration
- **WHEN** water level drops steadily across 24 hours
- **THEN** `sensor.<grow>_transpiration_rate_daily` reports the calculated daily volume or percentage loss

#### Scenario: Stalled water uptake warning
- **WHEN** a flowering grow space with lights operating experiences zero water level drop across 24 hours
- **THEN** `sensor.<grow>_transpiration_rate_daily` flags `stalled` in its consumption status
