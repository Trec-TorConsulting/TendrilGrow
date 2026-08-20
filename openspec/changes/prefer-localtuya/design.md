# Design: prefer-localtuya

## Context

RDWC header-bucket probes are Tuya Wi-Fi water testers. TendrilGrow today polls
them through `TuyaCloudClient` + `TendrilGrowTuyaCoordinator` and auto-maps the
resulting `TuyaMetricSensor` entities onto water roles. That path depends on the
Tuya IoT Core trial quota; polling burned it and suspended the project.

The original companion model (foundation) already assumed a Tuya HACS integration
would expose those probes as normal HA sensors. LocalTuya (`localtuya`, xZetsubou
fork) does that over LAN after a one-time IoT Core key fetch. Tuya Local
(`tuya_local`) is the fallback when a probe speaks protocol 3.5.

TendrilGrow must consume those HA entities, not replace LocalTuya, and must not
keep hitting OpenAPI while a local device is bound.

Constraints:
- One config entry per grow space; two tents means two probes — never auto-pick
  “any” LocalTuya sensor in the instance.
- No new Python packages; use HA device/entity registries (same pattern as pump
  power auto-discovery).
- Async-only; no LAN protocol implementation inside TendrilGrow.
- Secrets already in `SENSITIVE_KEYS` stay redacted.

## Goals / Non-Goals

**Goals:**
- Bind one local water-monitor HA device per grow space (`localtuya` preferred,
  then `tuya_local`).
- Auto-map that device’s water sensors onto unmapped water roles.
- Skip cloud polling whenever a local device is bound.
- Keep cloud OpenAPI polling as an explicit fallback when no local device is bound.
- Un-gate VPD and AI health sensors from `tuya_enabled`.
- Leave canopy air temp/humidity mapping to the operator (Vivosun).

**Non-Goals:**
- Implementing Tuya LAN protocol, local keys, or DP templates inside TendrilGrow.
- Installing or configuring LocalTuya / Tuya Local for the user.
- Removing the cloud client; it stays for fallback.
- Auto-mapping probe humidity/air-temp onto VPD roles.
- Running LocalTuya and Tuya Local against the same physical probe (operator
  concern; TendrilGrow binds one HA device).

## Decisions

### Source priority: local device, then cloud fallback
Effective water source for a grow space:

1. Bound HA device whose identifiers domain is `localtuya`
2. Else bound HA device whose identifiers domain is `tuya_local`
3. Else Tuya cloud polling, if `tuya_enabled` and credentials + device ids exist
4. Else manual sensor role mappings only

Rationale: LocalTuya is what the operator asked to prefer; Tuya Local is the
known protocol-3.5 escape hatch; cloud is what exhausted IoT Core.

Alternative considered: drop cloud entirely. Rejected — existing entries and
users without LocalTuya still need a path.

### Bind by HA `device_id`, not by guessing sensors
Store `CONF_WATER_MONITOR_DEVICE_ID` (Home Assistant device registry id) on the
config entry. Config/options use a device selector listing devices whose
identifier domain is in `{localtuya, tuya_local}`.

On setup, if that key is empty, try to match `CONF_TUYA_DEVICE_IDS` against
device-registry identifiers (`localtuya` first, then `tuya_local`). If exactly
one match for this space’s ids, persist it and treat as bound. If several
spaces share ids or none match, do not guess.

Rationale: two tents; a global “find any pH sensor” would cross-wire reservoirs.

### Classify local sensors by device_class, unit, then name
On the bound device, consider `sensor` entities (skip disabled/hidden) and map:

| Role | Match (first hit) |
| --- | --- |
| `ph` | `device_class == ph`, else name/id contains `ph` |
| `ec` | unit `mS/cm` or `µS/cm`/`uS/cm`, else name `ec` / `conductivity` |
| `tds` | unit `ppm`, else name `tds` |
| `orp` | unit `mV`, else name `orp` |
| `cf` | name `cf` (do not steal an EC entity) |
| `water_temperature` | `device_class == temperature` whose name contains `water`, else the sole temperature sensor on the device |

Never bind `humidity`, `temperature` (canopy), `battery`, or warning/number
config entities. If a role already has a mapping, leave it.

Rationale: LocalTuya DPs are numeric and OEM-shuffled; HA device_class/unit is
more stable than DP id. Probe “humidity” is not canopy RH.

### Cloud coordinator only when fallback is active
`TendrilGrowTuyaCoordinator` and `TuyaMetricSensor` entities are created only
when the effective source is cloud. A bound local device skips OpenAPI entirely
even if `tuya_enabled` is still true in stored options (local wins).

VPD and AI health entities move **out** of the `tuya_enabled` block in
`sensor.py`. Today they are created only when cloud Tuya is on; preferring
LocalTuya would otherwise delete them.

### Auto-map on add / reload, same store as today
Reuse `runtime.auto_mapped_sensor_roles` and `rebuild_automap`. Local auto-map
runs at grow-space setup (after registries are ready), not inside
`TuyaMetricSensor.async_added_to_hass`. Diagnostics report `water_source`
(`localtuya` | `tuya_local` | `cloud` | `none`) plus the bound HA device id.

### Config UX
- Mapping step: local water-monitor device selector first.
- Water-quality role fields stay visible when a local device is selected
  (override a bad DP).
- Those fields stay hidden only when cloud fallback is enabled and no local
  device is bound (current Tuya behavior).
- Cloud credential fields remain, labeled as fallback; default `tuya_enabled`
  stays false for new entries.

## Risks / Trade-offs

- **Wrong tent / wrong probe** → require an explicit or uniquely matched HA
  device id; never pick an unbound LocalTuya sensor.
- **DP scale wrong in LocalTuya** (pH 736 vs 7.36) → mapping fields stay
  visible so the operator can point at a corrected template sensor; TendrilGrow
  does not rescale LocalTuya states.
- **Protocol 3.5 / LocalTuya connect fail** → document Tuya Local as the
  companion fallback; TendrilGrow accepts either domain.
- **Two local integrations on one probe (port 6668)** → documented operator
  constraint; TendrilGrow binds one device only.
- **Stored `tuya_enabled` still true after local bind** → effective-source
  check ignores it; UI copy explains local wins. Do not silently rewrite the
  flag (avoids surprise diffs); optional later cleanup in options save.
- **Existing dashboard entity ids** (`sensor.*_tuya_7eizfw_*`) go stale when
  cloud sensors disappear → docs + `generate_dashboard.py`; not migrated
  automatically.

## Migration Plan

1. Ship the resolver and device selector; existing cloud entries keep polling
   until a local device is bound or matched from `tuya_device_ids`.
2. On first reload after LocalTuya devices exist, auto-bind when the Tuya
   device id matches exactly one local device; stop the coordinator for that
   entry.
3. Operator maps remaining gaps (or calls `tendrilgrow.rebuild_automap`).
4. Rollback: clear `CONF_WATER_MONITOR_DEVICE_ID` and re-enable cloud polling;
   cloud unique ids are unchanged.

## Open Questions

- None blocking. If DeviceSelector cannot OR `localtuya` and `tuya_local`,
  build the dropdown from the device registry in the flow (implementation
  detail).
