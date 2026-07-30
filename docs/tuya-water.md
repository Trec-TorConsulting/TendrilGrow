# Tuya water monitoring

TendrilGrow can optionally poll reservoir water monitors from the Tuya cloud and
expose normalized water-quality sensors. This is entirely optional — if you
already have water sensors in Home Assistant, map them directly instead.

## What it does

- Polls the Tuya cloud using a signed OpenAPI client.
- Normalizes device datapoints into consistent sensors.
- Creates per-device sensors and **auto-maps** them into the matching sensor
  roles so VPD, AI context, and dashboards work without manual wiring.

## Normalized sensors

Depending on your device, the following metrics are normalized:

| Sensor | Notes |
| --- | --- |
| pH | Reservoir pH. |
| EC | Electrical conductivity. |
| CF | Conductivity factor. |
| TDS | Total dissolved solids. |
| ORP | Oxidation-reduction potential. |
| Water Temperature | Reservoir/water probe temperature. |
| Humidity | Ambient humidity reported by the device. |
| Battery | Device battery percentage. |

!!! warning "Water temperature is not air temperature"
    Tuya water temperature maps to the `water_temperature` role, **not** the
    canopy air role used for VPD. You still map an **air** temperature/humidity
    sensor yourself for VPD.

## Enabling Tuya

During the **Map entities** step (or later in Options), enable Tuya and provide:

- Access ID and access secret
- Region
- Optional user UID
- Device IDs (comma-separated)
- Poll interval (seconds)

## Re-running auto-map

If you add devices or change mappings, call
[`tendrilgrow.rebuild_automap`](services.md#tendrilgrowrebuild_automap) to reload
entries and rebuild the auto-mapped sensor roles.

## Security

The Tuya access secret is sensitive and is redacted in diagnostics and logs.
Never share it in issues or discussions.
