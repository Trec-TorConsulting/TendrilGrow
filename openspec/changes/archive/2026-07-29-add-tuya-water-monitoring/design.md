# Design: add-tuya-water-monitoring

## Context

RDWC water probes in the maintainer's live setup are Tuya devices whose readings
are only exposed via the Tuya IoT cloud. This change (already implemented)
integrates that cloud as an optional per-grow-space data source and normalizes
its datapoints into TendrilGrow's water-quality roles. It is documented here so
`openspec/specs/` reflects shipped behavior.

Constraints:
- Async-only; use Home Assistant's shared aiohttp client session.
- No third-party Tuya SDK — sign requests directly to keep the install light.
- One coordinator per grow-space config entry (spaces stay isolated).
- Secrets (`tuya_access_secret`) must never be logged or exposed in diagnostics.

## Goals / Non-Goals

**Goals:**
- Poll Tuya cloud per grow space and expose normalized water-quality sensors.
- Auto-map Tuya metric entities to grow-space sensor roles to reduce setup burden.
- Tolerate partial/transient device failures without dropping all data.

**Non-Goals:**
- Local (LAN) Tuya control or command/write operations.
- Replacing the user's Tuya HACS integration for non-water devices.
- Actuating pumps/dosers (control actuation is a separate future change).

## Decisions

### Direct OpenAPI signing (no Tuya SDK)
`TuyaCloudClient` signs each request with HMAC-SHA256 over
`client_id + [access_token] + t + method + "\n" + SHA256(body) + "\n\n" + path`
and caches the access token until ~60s before expiry. Rationale: avoids a heavy
SDK dependency and keeps the manifest requirement list empty.

### Shadow-properties first, status fallback
`fetch_device_statuses` calls `/v2.0/cloud/thing/{id}/shadow/properties` and falls
back to `/v1.0/devices/{id}/status`. Rationale: newer devices expose richer,
scaled property shadows; older devices only expose v1 status. Both are normalized
through the same DP map.

### DP normalization + derivation
`normalize_tuya_statuses` maps a broad set of DP code aliases to stable keys
(`ph`, `ec`, `cf`, `orp`, `tds`, `water_temp_c`, `ambient_temp_c`,
`ambient_humidity`, `battery_pct`), applies Tuya `scale`, and heuristically
rescales unscaled integers (e.g., pH>14 ⇒ /100, EC>20 ⇒ /1000). When only one
conductivity measure is present it derives the others (TDS≈EC×500, EC≈TDS/500,
CF mirrors EC). Rationale: probes vary widely; downstream grow logic needs a
consistent metric set.

### Coordinator per entry with partial-failure tolerance
`TendrilGrowTuyaCoordinator` (interval = max(30s, configured)) polls each device;
it raises `UpdateFailed` only when **all** devices fail, otherwise logs partial
failures and returns what succeeded. It also refreshes device display names via
the user UID when provided.

### Role auto-mapping over manual mapping
When Tuya polling is enabled the manual water-quality mapping fields are hidden
(camera remains manual). On `async_added_to_hass`, a Tuya metric entity binds its
`entity_id` to the matching unmapped grow role and records it in
`auto_mapped_sensor_roles`. `rebuild_automap` reloads entries to recompute this.

## Risks / Trade-offs

- **Cloud dependency / rate limits** → configurable interval (≥30s) and token
  caching; partial-failure tolerance avoids flapping.
- **DP heuristics can misread exotic probes** → diagnostics expose effective and
  auto-mapped roles so users can verify; manual override remains possible by
  disabling Tuya polling.
- **Secret exposure** → `tuya_access_secret` in `SENSITIVE_KEYS`, redacted in
  diagnostics and never logged.

## Migration Plan

Additive and optional — disabled unless the user enables Tuya polling. Legacy
`ec_tds` role mappings are migrated to `tds` on model load. No breaking change to
existing entries.
