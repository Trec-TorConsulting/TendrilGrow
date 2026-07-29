# Proposal: add-tuya-water-monitoring

## Why

RDWC reservoirs are monitored by Tuya-cloud water probes (pH/EC/CF/ORP/TDS) that
have no reliable local API. To score grow health and drive advice, TendrilGrow
needs those readings as first-class Home Assistant sensors and mapped grow roles
without the user hand-wiring every entity. This capability is **already shipped**;
this change documents it retroactively so the specs match the code.

## What Changes

- Add an optional **Tuya cloud polling** path per grow space: the user enables it
  and provides Tuya IoT access id/secret, region, optional user UID, and a list
  of device ids; TendrilGrow polls the Tuya OpenAPI on a configurable interval.
- Add a **Tuya OpenAPI client** (`tuya_client.py`) with HMAC-SHA256 request
  signing, token caching, device listing, and device-status fetch that prefers
  the v2.0 shadow-properties endpoint and falls back to the v1.0 status endpoint.
- Add **datapoint (DP) normalization** that maps heterogeneous Tuya DP codes to a
  stable metric set (pH, EC, CF, ORP, TDS, water temperature, ambient
  humidity/temperature, battery) and derives EC↔TDS↔CF when a probe reports only
  one conductivity measure.
- Add a **DataUpdateCoordinator** (`coordinator.py`) that polls per grow space,
  tracks per-device display names and last-updated timestamps, and tolerates
  partial device failures (only fails the update when every device fails).
- Add **Tuya-backed sensor entities** (`sensor.py`): one entity per device per
  metric plus a per-device diagnostic "Last Updated" timestamp, grouped under a
  Home Assistant device per Tuya probe.
- Add **role auto-mapping**: when a Tuya metric entity is added and the matching
  grow-space sensor role is unmapped, bind that role to the new entity id, and
  hide the manual sensor-mapping fields while Tuya polling is enabled (camera
  stays manual).
- Add a **`rebuild_automap` service** that reloads one or all loaded TendrilGrow
  entries to rebuild Tuya auto-mapping.
- Extend diagnostics to report `auto_mapped_sensor_roles` and effective sensor
  mappings, and redact the Tuya access secret.

## Capabilities

### New Capabilities
- `tuya-water-monitoring`: Optional per-grow-space Tuya cloud polling — client,
  DP normalization, coordinator, metric + last-updated sensors, role
  auto-mapping, the `rebuild_automap` service, and secret redaction.

### Modified Capabilities
- `grow-data-model`: The sensor-role registry splits the former combined `EC/TDS`
  role into distinct `ec`, `cf`, `orp`, and `tds` roles (with legacy `ec_tds`
  migrated to `tds`), so Tuya water-quality metrics bind to dedicated roles.

## Impact

- **New code**: `custom_components/tendrilgrow/tuya_client.py`,
  `coordinator.py`; Tuya sensor entities and auto-mapping in `sensor.py`; Tuya
  config/options fields in `config_flow.py`; `rebuild_automap` in `__init__.py`
  and `services.yaml`.
- **Constants**: `CONF_TUYA_*` keys, `SENSOR_ROLE_CF/ORP/TDS`,
  `SENSOR_ROLE_EC_TDS_LEGACY`, `SENSOR_ROLES_TUYA_OPTIONAL`, and
  `tuya_access_secret` added to `SENSITIVE_KEYS`.
- **Config/UX**: New optional Tuya section in the config and options flows; manual
  water-quality sensor mappings are hidden when Tuya polling is enabled.
- **External dependency**: Tuya IoT Platform cloud project (access id/secret) and
  network egress to `openapi.tuya{us,eu,cn,in}.com`. No new Python packages —
  requests use Home Assistant's shared aiohttp session.
- **Secrets**: `tuya_access_secret` is stored in config-entry data and redacted
  from logs and diagnostics.
