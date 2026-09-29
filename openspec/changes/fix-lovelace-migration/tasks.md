## 1. Stop dashboard writes

- [x] 1.1 Remove the delayed Lovelace load/save scheduled from config entry setup
- [x] 1.2 Keep entity-registry migration for TendrilGrow entities

## 2. Repair

- [x] 2.1 Add a read-only scan for retired week-in-stage entity ids in storage dashboards
- [x] 2.2 Raise a repair that names the retired id and the replacement id, and dismiss it when the scan is clean
- [x] 2.3 Add repair strings

## 3. Tests

- [x] 3.1 Setup does not call dashboard save
- [x] 3.2 A dashboard config containing the retired id creates a repair and is not modified

