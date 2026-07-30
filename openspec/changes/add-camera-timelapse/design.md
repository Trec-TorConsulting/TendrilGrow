# Design: add-camera-timelapse

## Context

TendrilGrow maps a `camera` per grow space for AI vision checks. This change
samples that camera over time to build a grow time-lapse using the existing
snapshot mechanism. Two Home Assistant constraints shape the design:
`camera.snapshot` only writes inside `allowlist_external_dirs`, and turning frames
into a video needs ffmpeg run off the event loop.

## Goals / Non-Goals

**Goals**

- Opt-in, low-maintenance periodic capture of the mapped camera per space.
- Bounded disk footprint via frame retention.
- Clear status entities, a one-press capture, and a video-assembly service.
- Fail loudly and helpfully when the capture directory is not allow-listed.

**Non-Goals**

- No new camera streaming/recording pipeline; reuse `camera.snapshot`.
- No cloud upload or external storage.
- No always-on high-frequency capture; the interval is coarse (hours) by default.

## Capture pipeline

- **Directory**: default `<config>/www/tendrilgrow/<slug>/timelapse/`, served at
  `/local/tendrilgrow/<slug>/timelapse/...`; overridable via `CONF_TIMELAPSE_DIR`.
- **Snapshot**: call `camera.snapshot` with the mapped camera and a timestamped
  filename (`frame-YYYYMMDD-HHMMSS.jpg`). Verify the write succeeded; on an
  allow-list failure, raise a repair issue (below) instead of silently looping.
- **Triggers**: (a) a per-space scheduler at `CONF_TIMELAPSE_INTERVAL_HOURS`
  (default 24), started only when `CONF_TIMELAPSE_ENABLED`; (b) a "Capture Frame"
  button; (c) a `capture_timelapse_frame` service.
- **Retention**: after each capture, prune the directory to the newest
  `CONF_TIMELAPSE_RETENTION_FRAMES` frames (default 120) to bound disk usage.

## Video assembly

- A `build_timelapse` service runs ffmpeg over the frames (glob input pattern,
  fixed output framerate) using the binary from
  `homeassistant.components.ffmpeg`, executed via an async subprocess so the event
  loop is never blocked.
- When ffmpeg is unavailable, the service degrades to a no-op that logs the
  equivalent manual command; captured frames remain intact.

## Entities and services

- `button.<grow>_capture_timelapse_frame` — capture now.
- `sensor.<grow>_timelapse_frames` — frame count, with the capture directory and
  the latest-frame path as attributes.
- `sensor.<grow>_timelapse_last_frame` — timestamp of the newest frame.
- Services: `capture_timelapse_frame(entry_id)`, `build_timelapse(entry_id)`.

## Failure handling (Repairs)

- If a capture fails because the directory is not allow-listed, raise a repair
  issue (`timelapse_not_allowlisted`) that names the exact path to add to
  `allowlist_external_dirs`, and pause the scheduler until captures succeed again.

## Config (`const.py`, options flow)

- `CONF_TIMELAPSE_ENABLED` (bool, default **False**) — opt-in.
- `CONF_TIMELAPSE_INTERVAL_HOURS` (int, default 24).
- `CONF_TIMELAPSE_RETENTION_FRAMES` (int, default 120).
- `CONF_TIMELAPSE_DIR` (str, optional; default computed from the space slug).

## Testing

- Unit-test the pure helpers: the timestamped-filename builder, the retention
  prune selector (given files + cap → files to delete), directory/URL resolution,
  and the ffmpeg command builder.
- Exercise the capture path with a temp directory and a fake `hass`; assert the
  allow-list repair is raised on a simulated failure and that ffmpeg absence
  degrades gracefully.
