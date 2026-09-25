## ADDED Requirements

### Requirement: Editable target bands
Each grow space SHALL expose restore-state number entities for pH low, pH high, EC low, EC high, VPD low, and VPD high, grouped on the grow-space device. When a band has no restored operator value, the integration MUST seed it from the current stage's target table. Changing the growth stage MUST NOT overwrite a band the operator has edited.

#### Scenario: New space is seeded from the stage
- **WHEN** a grow space is in `vegetative` and the operator has not set a pH band
- **THEN** the pH low and high entities match the vegetative stage table

#### Scenario: Stage change keeps an operator band
- **WHEN** the operator has set pH high to 6.2 and then changes the growth stage
- **THEN** pH high remains 6.2

### Requirement: Light schedule clock
Each grow space SHALL expose a lights-on time and a lights-off time. When both are set, lights-on hours MUST equal the duration between them, including a schedule that crosses midnight. These values MUST be included in the AI health-check cultivation context.

#### Scenario: Overnight photoperiod
- **WHEN** lights-on is 18:00 and lights-off is 12:00
- **THEN** lights-on hours is 18

#### Scenario: Prompt includes the band and schedule
- **WHEN** an AI health check runs and the operator has set an EC band and light times
- **THEN** the prompt contains that EC band and those light times

### Requirement: Targets do not touch water credentials
Creating or editing target and schedule entities MUST NOT modify `water_monitor_device_id`, Tuya access id, Tuya access secret, Tuya device ids, or any LocalTuya or Tuya Local config entry.

#### Scenario: Editing a target keeps the water binding
- **WHEN** the operator changes target pH low
- **THEN** the stored water-monitor device id and Tuya secret are unchanged
