## 1. Stop dashboard writes

- [ ] 1.1 Remove the delayed Lovelace load/save scheduled from config entry setup
- [ ] 1.2 Keep entity-registry migration for TendrilGrow entities

## 2. Repair

- [ ] 2.1 Add a read-only scan for retired week-in-stage entity ids in storage dashboards
- [ ] 2.2 Raise a repair that names the retired id and the replacement id, and dismiss it when the scan is clean
- [ ] 2.3 Add repair strings

## 3. Tests

- [ ] 3.1 Setup does not call dashboard save
- [ ] 3.2 A dashboard config containing the retired id creates a repair and is not modified
