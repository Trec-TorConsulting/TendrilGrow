## ADDED Requirements

### Requirement: Preserve local water binding and stored keys
The integration MUST persist `water_monitor_device_id`, Tuya device ids, Tuya access id, and Tuya access secret across options saves, entry reloads, and local auto-bind. A blank or omitted secret or device field MUST keep the stored value. The integration MUST NOT clear these fields as a side effect of saving mappings, disabling cloud polling, or failing a cloud request.

#### Scenario: Blank secret keeps the stored secret
- **WHEN** the operator saves options and leaves the Tuya access secret blank
- **THEN** the previously stored access secret is unchanged

#### Scenario: Options save keeps the bound water monitor
- **WHEN** the operator saves options without changing the water-monitor device
- **THEN** `water_monitor_device_id` is still the previously bound device id

#### Scenario: Auto-bind does not replace an existing device id
- **WHEN** a grow space already has `water_monitor_device_id` set and a different local device also matches stored Tuya device ids
- **THEN** the integration keeps the stored device id

### Requirement: Do not modify LocalTuya or Tuya Local config
The integration MUST NOT read `local_key` values into its own config entry, log them, or call update/reload on `localtuya` or `tuya_local` config entries.

#### Scenario: Options save leaves companion config alone
- **WHEN** the operator saves TendrilGrow options for a space bound to a LocalTuya device
- **THEN** the LocalTuya config entry is not updated

### Requirement: Bound local device remains the water source
When a grow space has a bound `localtuya` or `tuya_local` water-monitor device, water-quality readings MUST come from that device's Home Assistant entities. This change MUST NOT start Tuya cloud polling and MUST NOT change cloud datapoint scaling.

#### Scenario: LocalTuya space does not poll the cloud
- **WHEN** a grow space has a bound LocalTuya water monitor
- **THEN** the integration does not create a Tuya cloud coordinator for that space

#### Scenario: Cloud scaling code is unchanged
- **WHEN** this change is applied
- **THEN** Tuya cloud datapoint normalization behavior is unmodified
