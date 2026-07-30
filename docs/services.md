# Services

TendrilGrow registers six services under the `tendrilgrow` domain. Call them
from **Developer Tools → Actions**, scripts, or automations.

## `tendrilgrow.run_ai_health_check`

Run a camera-based AI health analysis for one or all loaded entries.

| Field | Required | Description |
| --- | --- | --- |
| `entry_id` | No | Specific config entry to run. Omit to run all loaded entries. |
| `reason` | No | Optional reason string recorded with the result. |

```yaml
action: tendrilgrow.run_ai_health_check
data:
  reason: Manual check after top-dressing
```

## `tendrilgrow.rebuild_automap`

Reload TendrilGrow entries to rebuild Tuya auto-mapped sensor roles.

| Field | Required | Description |
| --- | --- | --- |
| `entry_id` | No | Specific config entry to reload. Omit to reload all loaded entries. |

```yaml
action: tendrilgrow.rebuild_automap
```

## `tendrilgrow.set_pump`

Control a mapped pump.

| Field | Required | Description |
| --- | --- | --- |
| `entry_id` | Yes | The config entry that contains the pump mapping. |
| `pump` | Yes | One of `rdwc_pump`, `chiller_pump`, `air_pump`. |
| `action` | Yes | One of `on`, `off`, `toggle`. |

```yaml
action: tendrilgrow.set_pump
data:
  entry_id: 0123456789abcdef0123456789abcdef
  pump: rdwc_pump
  action: "on"
```

## `tendrilgrow.mark_flush`

Record that a full reservoir flush and refill was just completed.

| Field | Required | Description |
| --- | --- | --- |
| `entry_id` | Yes | The config entry whose reservoir was flushed. |

```yaml
action: tendrilgrow.mark_flush
data:
  entry_id: 0123456789abcdef0123456789abcdef
```

## `tendrilgrow.capture_timelapse_frame`

Capture one timelapse frame now.

| Field | Required | Description |
| --- | --- | --- |
| `entry_id` | No | Specific config entry to capture for. Omit to capture for all loaded entries. |

```yaml
action: tendrilgrow.capture_timelapse_frame
data:
  entry_id: 0123456789abcdef0123456789abcdef
```

!!! warning "Allow-list required"
    Snapshot writes are blocked unless the capture directory is in
    `homeassistant.allowlist_external_dirs`. Default path:
    `/config/www/tendrilgrow/<grow_slug>/timelapse/`.

## `tendrilgrow.build_timelapse`

Build an MP4 timelapse from captured frames.

| Field | Required | Description |
| --- | --- | --- |
| `entry_id` | Yes | The config entry whose timelapse should be built. |

```yaml
action: tendrilgrow.build_timelapse
data:
  entry_id: 0123456789abcdef0123456789abcdef
```

!!! note "ffmpeg"
    This service uses Home Assistant's ffmpeg component binary. If ffmpeg is not
    available, TendrilGrow logs the equivalent manual command and leaves frames
    untouched.

!!! tip "Finding an entry ID"
    Open **Settings → Devices & Services → TendrilGrow**, choose the entry, and
    copy the ID from the browser URL, or use the entry picker in the visual
    action editor.
