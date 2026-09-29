# Proposal: prefer-localtuya

## Why

TendrilGrow currently polls the Tuya IoT Core cloud for header-bucket water
metrics. That path exhausted the trial API quota and suspended the project; the
same quota will burn again if cloud polling stays the default. The probes already
speak Tuya’s LAN protocol, and Home Assistant can expose them through LocalTuya
(`localtuya`, xZetsubou fork) — or Tuya Local (`tuya_local`) when a probe needs
protocol 3.5. TendrilGrow should prefer those local entities so live pH/EC/TDS
never depend on IoT Core.

## What Changes

- Prefer a **LocalTuya device** (then Tuya Local) as the water-metric source for
  each grow space: bind one HA device per space and auto-map its sensors onto
  `ph`, `ec`, `cf`, `orp`, `tds`, and `water_temperature`.
- **Do not auto-map** the probe’s ambient humidity or temperature onto the canopy
  `humidity` / `temperature` roles (those stay Vivosun / operator-mapped for VPD).
- **Skip Tuya cloud polling** when a local device is bound. Cloud OpenAPI polling
  remains an optional fallback for spaces with no local device.
- Add a **device selector** in config/options for the local water monitor; reuse
  stored Tuya device ids to auto-bind a matching `localtuya` / `tuya_local`
  device on existing entries.
- Keep water-quality mapping fields visible when a local source is used so the
  operator can override a bad DP; hide them only for the cloud-poll fallback
  (same as today).
- Demote cloud credentials in the UI (fallback, default off for new spaces).
- **Un-gate** VPD and AI health sensor creation from `tuya_enabled` so disabling
  cloud polling does not drop those entities.
- Update docs (Tuya water, install, troubleshooting) so LocalTuya is the
  recommended path and IoT Core is described as key-extraction only.

## Capabilities

### New Capabilities

- _(none)_

### Modified Capabilities

- `tuya-water-monitoring`: Water metrics prefer LocalTuya / Tuya Local HA
  devices; cloud polling is fallback-only and must not run while a local device
  is bound; auto-map from the bound local device; `rebuild_automap` covers the
  local source; probe humidity/temp must not bind to canopy roles.
- `grow-space-config`: Config/options gain a local water-monitor device selector
  and treat cloud Tuya fields as optional fallback rather than the primary
  mapping path.

## Impact

- **Code**: new local-device resolver (entity/device registry, same pattern as
  pump power auto-discovery); auto-map from that device; `config_flow.py` device
  selector + fallback cloud fields; `sensor.py` must create VPD/AI entities
  independently of Tuya cloud; coordinator starts only when cloud fallback is
  actually in use.
- **Constants**: local-device config key (HA `device_id`); source-priority
  helper; water-role set used for local auto-map (no canopy humidity).
- **Docs**: `docs/tuya-water.md`, `docs/installation.md`,
  `docs/configuration.md`, `docs/troubleshooting.md`, README companion list.
- **No new Python packages**. LocalTuya / Tuya Local remain companion
  integrations the operator installs; TendrilGrow only consumes their entities.
- **Existing entries**: keep working. If a matching local device is found for a
  stored Tuya device id, bind it and stop cloud polling; otherwise cloud
  fallback continues until the operator selects a local device.
- **Not breaking**: cloud polling is not removed; entity unique ids for
  TendrilGrow’s own cloud Tuya sensors stay the same when the fallback is used.
