## 1. Band evaluation

- [x] 1.1 Subscribe to mapped pH, EC, and derived VPD and compare them to operator bands or `STAGE_TARGETS`
- [x] 1.2 Expose problem binary sensors for pH, EC, VPD, and a summary
- [x] 1.3 Leave the binary sensor off when the stage has no band, and unavailable when the source is unavailable

## 2. Notify

- [x] 2.1 Notify on the in-range to out-of-range edge using the existing notify service, with a 6-hour cooldown
- [x] 2.2 Do not call pump, light, or fan services from the monitor
- [x] 2.3 Do not start a Tuya cloud coordinator and do not read or write LocalTuya config

## 3. Tests

- [x] 3.1 pH above the band turns the pH binary sensor on
- [x] 3.2 An operator band overrides the stage table
- [x] 3.3 Repeated updates while still out of range do not notify again inside the cooldown
- [x] 3.4 A `dry` stage does not raise a pH band alert
