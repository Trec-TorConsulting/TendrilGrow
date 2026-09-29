## ADDED Requirements

### Requirement: Total pump power uses registry entity ids
The total pump power sensor SHALL subscribe to each per-pump power sensor by resolving its entity id from the entity registry `unique_id` `{entry_id}_{pump_role}_power`. It MUST NOT subscribe to an entity id guessed from the config entry id. When a per-pump power sensor updates, the total MUST update to the sum of the available per-pump readings.

#### Scenario: Total follows a real pump power sensor
- **WHEN** the RDWC pump power sensor reports 40 W and its entity id is not `sensor.{entry_id}_rdwc_pump_power`
- **THEN** the total pump power sensor includes that 40 W

#### Scenario: Pump turned off drops out of the sum
- **WHEN** one pump power sensor becomes unavailable and another reports 12 W
- **THEN** the total reports 12 W

### Requirement: Daily energy uses duty cycle
Estimated daily pump energy SHALL be the sum over mapped pumps of last-known watts times hours that pump's switch has been on during the local day, divided by 1000. The cost sensor SHALL multiply that energy by the configured price per kWh. Both sensors MUST expose `estimated: true`. The integration MUST NOT multiply instantaneous watts by 24 when the pump switch state is known.

#### Scenario: Pump on for one hour
- **WHEN** a pump drawing 100 W has been on for 1 hour today and off otherwise, and price is 0.20 per kWh
- **THEN** estimated energy is 0.1 kWh and estimated cost is 0.02

#### Scenario: Switch off contributes no energy
- **WHEN** a pump's switch is off for the whole local day
- **THEN** that pump contributes 0 kWh to the daily estimate

### Requirement: Power resolution uses merged mappings
Pump switch creation and power-source resolution MUST use the merged config entry (data overlaid by options). A pump role present only in options MUST be included.

#### Scenario: Options-only pump is counted
- **WHEN** `rdwc_pump` is mapped in options and not in entry data, and that outlet's device has a power sensor
- **THEN** the entry exposes that pump's power sensor and includes it in the total
