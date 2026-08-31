# Tuya / LocalTuya water monitoring

TendrilGrow prefers **LocalTuya** (or **Tuya Local**) Home Assistant devices for
reservoir water metrics. Those integrations talk to the probe over LAN after a
one-time local-key fetch. Cloud OpenAPI polling is an optional fallback only —
it burns Tuya IoT Core quota and should stay off when a local device is bound.

## Recommended path: LocalTuya

1. Install [LocalTuya](https://github.com/xZetsubou/hass-localtuya) (HACS) — or
   [Tuya Local](https://github.com/make-all/tuya-local) if your probe needs
   protocol 3.5.
2. Add each water probe as a LocalTuya / Tuya Local device (use IoT Core only
   long enough to extract the local key / DP map; then stop cloud polling there
   too).
3. In TendrilGrow setup or Options, pick that HA device under **Local water
   monitor**. TendrilGrow auto-maps pH, EC, CF, ORP, TDS, and water temperature
   from that device’s sensors.
4. Still map **canopy** air temperature and humidity yourself (for VPD). The
   probe’s ambient humidity / air temp are **not** auto-mapped onto those roles.

Do **not** run LocalTuya and Tuya Local against the same physical probe (both
use LAN port 6668). Bind one HA device per grow space — two tents need two
probes and two bindings.

## Cloud fallback (optional)

If no local device is bound, you can enable Tuya cloud polling with:

- Access ID and access secret
- Region
- Optional user UID
- Device IDs (comma-separated)
- Poll interval (seconds; **default 600** / 10 minutes)

When cloud is the effective source, TendrilGrow creates per-device metric
sensors and auto-maps water roles. A bound local device **always wins**: no
OpenAPI requests are made for that grow space even if `tuya_enabled` is still
true in stored options.

## Normalized metrics

| Sensor | Notes |
| --- | --- |
| pH | Reservoir pH. |
| EC | Electrical conductivity. |
| CF | Conductivity factor. |
| TDS | Total dissolved solids. |
| ORP | Oxidation-reduction potential. |
| Water Temperature | Reservoir/water probe temperature. |
| Humidity | Probe ambient humidity (cloud entity only; not canopy RH). |
| Battery | Device battery percentage (cloud entity only). |

!!! warning "Water temperature is not air temperature"
    Water temperature maps to the `water_temperature` role, **not** the canopy
    air role used for VPD. Map an **air** temperature/humidity sensor for VPD.

## Re-running auto-map

If you add LocalTuya devices or change bindings, call
[`tendrilgrow.rebuild_automap`](services.md#tendrilgrowrebuild_automap) to reload
entries and rebuild local and cloud auto-mapped roles.

## Dashboard entity ids

When you switch from cloud Tuya sensors to LocalTuya entities, dashboard
references such as `sensor.*_tuya_*` go stale. Regenerate the Lovelace
dashboard with `scripts/generate_dashboard.py` (see [Dashboards](dashboards.md)),
or update entity ids manually.

## Security

The Tuya access secret is sensitive and is redacted in diagnostics and logs.
Never share it in issues or discussions. Prefer LocalTuya so the secret is only
needed for a one-time key extraction.
