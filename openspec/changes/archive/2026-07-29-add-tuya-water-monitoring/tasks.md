# Tasks: add-tuya-water-monitoring

> Retroactive change. All tasks are **complete** — they document code already
> shipped in `custom_components/tendrilgrow/`. Checkboxes reflect implemented and
> tested behavior.

## 1. Tuya OpenAPI client

- [x] 1.1 Implement `TuyaCloudClient` with HMAC-SHA256 signing and token caching (`tuya_client.py`)
- [x] 1.2 Support regional endpoints (us/eu/cn/in)
- [x] 1.3 Implement `list_user_devices(uid)` and `fetch_device_statuses(device_id)` with shadow-properties-first, status fallback
- [x] 1.4 Raise `TuyaApiError` on unsuccessful Tuya responses

## 2. Datapoint normalization

- [x] 2.1 Map Tuya DP code aliases to stable metric keys in `normalize_tuya_statuses`
- [x] 2.2 Apply reported `scale` and heuristic rescaling for pH/EC/temperature
- [x] 2.3 Derive EC/TDS/CF when only one conductivity measure is present
- [x] 2.4 Unit tests for scaled, TDS-only, and EC-only normalization (`tests/test_tuya_client.py`)

## 3. Coordinator

- [x] 3.1 Implement `TendrilGrowTuyaCoordinator` (one per entry, interval ≥ 30s)
- [x] 3.2 Track per-device display names and last-updated timestamps
- [x] 3.3 Tolerate partial device failures; fail only when all devices fail
- [x] 3.4 Refresh device names via user UID when provided

## 4. Sensor entities and roles

- [x] 4.1 Add `TuyaMetricSensor` (per device per metric) with device grouping and units
- [x] 4.2 Add `TuyaLastUpdatedSensor` (diagnostic timestamp)
- [x] 4.3 Report unavailable when a metric is missing from the latest reading
- [x] 4.4 Auto-map Tuya metric entities to unmapped grow roles on add
- [x] 4.5 Split water roles into `ec`, `cf`, `orp`, `tds`; migrate legacy `ec_tds` → `tds` (`const.py`, `models/grow.py`)

## 5. Config, service, and diagnostics

- [x] 5.1 Add Tuya fields to config and options flows; hide manual water roles when Tuya enabled
- [x] 5.2 Add `CONF_TUYA_*` constants and `SENSOR_ROLES_TUYA_OPTIONAL`
- [x] 5.3 Register the `rebuild_automap` service (`__init__.py`, `services.yaml`)
- [x] 5.4 Add `tuya_access_secret` to `SENSITIVE_KEYS`; report auto-mapped/effective roles in diagnostics
- [x] 5.5 Add `strings.json` / `translations/en.json` labels for Tuya fields
