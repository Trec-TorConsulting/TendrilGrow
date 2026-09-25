## 1. Total power subscription

- [x] 1.1 Resolve per-pump power sensors through the entity registry `unique_id` and subscribe the total sensor to those entity ids
- [x] 1.2 Remove the guessed `sensor.{entry_id}_{role}_power` subscription
- [x] 1.3 Read pump control and power mappings from merged config

## 2. Duty-cycle energy

- [x] 2.1 Track local-day on-time for each pump switch and persist it across restart
- [x] 2.2 Compute daily kWh from watts times hours-on, and cost from that energy times price
- [x] 2.3 Set `estimated: true` and stop using a fixed 24-hour multiplier when switch state is known

## 3. Tests

- [x] 3.1 Total power updates when the real pump power entity id differs from the guessed id
- [x] 3.2 A pump on for one hour at 100 W yields 0.1 kWh
- [x] 3.3 A pump switch that stays off contributes 0 kWh
