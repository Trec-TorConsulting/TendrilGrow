## 1. Target band entities

- [x] 1.1 Add restore-state number entities for pH, EC, and VPD low and high on the grow-space device
- [x] 1.2 Seed unset bands from the current stage table
- [x] 1.3 Skip reseed on stage change when the operator has edited that band

## 2. Light schedule

- [x] 2.1 Add lights-on and lights-off time entities
- [x] 2.2 Update lights-on hours from those times, including a midnight crossing
- [x] 2.3 Include the band and light times in the AI health-check context labels

## 3. Tests

- [x] 3.1 A new vegetative space seeds the vegetative pH band
- [x] 3.2 Changing stage keeps an operator-edited pH high value
- [x] 3.3 Lights 18:00 to 12:00 yields 18 hours on
- [x] 3.4 Editing a target does not change `water_monitor_device_id` or the Tuya secret
